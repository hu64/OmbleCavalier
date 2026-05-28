"""
Convert omblecavalier.nnue → omblecavalier.onnx without PyTorch.

Reconstructs the full computation graph (L1 linear → SCReLU → per-bucket
output heads → bucket gather) using the onnx graph builder.  The resulting
model is byte-for-byte equivalent to what export.py + torch.onnx.export
produces, but requires only onnx + numpy.

Usage:
    python nnue_to_onnx.py [input.nnue] [output.onnx]
"""
import struct
import sys

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

MAGIC   = b"NNUE"
VERSION = 2


def load_nnue(path: str):
    with open(path, "rb") as f:
        if f.read(4) != MAGIC:
            raise ValueError("Not a .nnue file")
        version, n_buckets = struct.unpack("<BB", f.read(2))
        if version != VERSION:
            raise ValueError(f"Unsupported version {version}")
        n0, n1 = struct.unpack("<II", f.read(8))

        w1    = np.frombuffer(f.read(n1 * n0 * 4), dtype="<f4").reshape(n1, n0).copy()
        b1    = np.frombuffer(f.read(n1 * 4),      dtype="<f4").copy()
        w_out = np.frombuffer(f.read(n_buckets * n1 * 4), dtype="<f4").reshape(n_buckets, n1).copy()
        b_out = np.frombuffer(f.read(n_buckets * 4),      dtype="<f4").copy()

    return n0, n1, n_buckets, w1, b1, w_out, b_out


def build_onnx(n0, n1, n_buckets, w1, b1, w_out, b_out) -> onnx.ModelProto:
    nodes = []
    initializers = []

    def init(name, arr):
        initializers.append(numpy_helper.from_array(arr, name=name))

    # ── Weights ──────────────────────────────────────────────────────────────
    init("w1",    w1)        # (N1, N0)
    init("b1",    b1)        # (N1,)
    init("w_out", w_out)     # (N_BUCKETS, N1)
    init("b_out", b_out)     # (N_BUCKETS,)

    # Constants
    zero  = np.array(0.0, dtype=np.float32)
    one   = np.array(1.0, dtype=np.float32)
    n_bkt = np.array(n_buckets, dtype=np.int64)
    c32   = np.array(32, dtype=np.int64)
    init("const_zero",  zero)
    init("const_one",   one)
    init("const_nbkt",  n_bkt)
    init("const_32",    c32)

    # ── L1: x1 = SCReLU(W1 @ x + b1) ────────────────────────────────────────
    # features: (batch, N0) → Gemm → (batch, N1)
    nodes.append(helper.make_node(
        "Gemm", ["features", "w1", "b1"], ["l1_out"],
        transB=1,
    ))
    # SCReLU: clamp(l1_out, 0, 1)²
    nodes.append(helper.make_node("Clip", ["l1_out", "const_zero", "const_one"], ["clipped"]))
    nodes.append(helper.make_node("Mul",  ["clipped", "clipped"], ["x1"]))

    # ── Bucket index from piece count ─────────────────────────────────────────
    # opset 13: ReduceSum takes axes as an input tensor, not attribute
    init("axes_1", np.array([1], dtype=np.int64))
    nodes.append(helper.make_node(
        "ReduceSum", ["features", "axes_1"], ["piece_count_f"],
        keepdims=0,
    ))
    # cast to int64
    nodes.append(helper.make_node(
        "Cast", ["piece_count_f"], ["piece_count"],
        to=TensorProto.INT64,
    ))
    # bucket = clamp((32 - piece_count) * N_BUCKETS // 32, 0, N_BUCKETS-1)
    nodes.append(helper.make_node("Sub", ["const_32", "piece_count"], ["diff"]))
    nodes.append(helper.make_node("Mul", ["diff", "const_nbkt"],      ["scaled"]))
    nodes.append(helper.make_node("Div", ["scaled", "const_32"],      ["bucket_raw"]))
    # Cast → float Clip → Cast back (int64 Clip is non-portable)
    nodes.append(helper.make_node("Cast", ["bucket_raw"], ["bucket_f"], to=TensorProto.FLOAT))
    init("clamp_lo", np.array(0.0, dtype=np.float32))
    init("clamp_hi", np.array(float(n_buckets - 1), dtype=np.float32))
    nodes.append(helper.make_node("Clip", ["bucket_f", "clamp_lo", "clamp_hi"], ["bucket_cf"]))
    nodes.append(helper.make_node("Cast", ["bucket_cf"], ["bucket"], to=TensorProto.INT64))

    # ── All output heads: (N_BUCKETS, N1) × (batch, N1)ᵀ + bias ─────────────
    # all_logits shape: (batch, N_BUCKETS)
    # x1: (batch, N1), w_out: (N_BUCKETS, N1) → MatMul(x1, w_outᵀ) = (batch, N_BUCKETS)
    nodes.append(helper.make_node("Transpose", ["w_out"], ["w_out_T"], perm=[1, 0]))
    nodes.append(helper.make_node("MatMul", ["x1", "w_out_T"], ["all_logits_no_bias"]))
    nodes.append(helper.make_node("Add", ["all_logits_no_bias", "b_out"], ["all_logits"]))

    # ── Gather the right bucket per sample ───────────────────────────────────
    # opset 13: Unsqueeze/Squeeze take axes as input tensors
    init("axes_1i", np.array([1], dtype=np.int64))
    nodes.append(helper.make_node("Unsqueeze", ["bucket", "axes_1i"], ["bucket_2d"]))
    nodes.append(helper.make_node(
        "GatherElements", ["all_logits", "bucket_2d"], ["logit_2d"],
        axis=1,
    ))
    nodes.append(helper.make_node("Squeeze", ["logit_2d", "axes_1i"], ["logit"]))
    nodes.append(helper.make_node("Unsqueeze", ["logit", "axes_1i"], ["logit_out"]))

    # ── Graph ─────────────────────────────────────────────────────────────────
    graph = helper.make_graph(
        nodes,
        "OmbleCavalierNNUE",
        inputs=[
            helper.make_tensor_value_info("features", TensorProto.FLOAT, ["batch", n0]),
        ],
        outputs=[
            helper.make_tensor_value_info("logit_out", TensorProto.FLOAT, ["batch", 1]),
        ],
        initializer=initializers,
    )

    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    model.ir_version = 8
    onnx.checker.check_model(model)
    return model


def main():
    nnue_path = sys.argv[1] if len(sys.argv) > 1 else "omblecavalier.nnue"
    onnx_path = sys.argv[2] if len(sys.argv) > 2 else nnue_path.replace(".nnue", ".onnx")

    print(f"Loading: {nnue_path}")
    n0, n1, n_buckets, w1, b1, w_out, b_out = load_nnue(nnue_path)
    print(f"  Architecture: {n0} → {n1} (SCReLU) → {n_buckets}-bucket output")

    model = build_onnx(n0, n1, n_buckets, w1, b1, w_out, b_out)
    onnx.save(model, onnx_path)

    import os
    print(f"Exported: {onnx_path}  ({os.path.getsize(onnx_path)/1024:.1f} KB)")


if __name__ == "__main__":
    main()
