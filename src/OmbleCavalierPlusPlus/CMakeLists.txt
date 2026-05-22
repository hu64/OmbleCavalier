cmake_minimum_required(VERSION 3.10)
project(OmbleCavalier++ CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF) # optional, avoids compiler-specific extensions
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -march=native")

include(CheckIPOSupported)
check_ipo_supported(RESULT ipo_supported)
if(ipo_supported)
    set(CMAKE_INTERPROCEDURAL_OPTIMIZATION TRUE)
endif()

# Enable CTest
enable_testing()
include(CTest)

# Add include folder”
include_directories(${PROJECT_SOURCE_DIR}/include)

# Executable
add_executable(omble_cavalier++
    src/main.cpp
    src/search.cpp
    src/eval.cpp
    src/nnue.cpp
    src/tt.cpp
    src/book.cpp
    src/utils.cpp
    src/puzzles.cpp
)

add_executable(test_pawnstructure
    src/test_pawnstructure.cpp
    src/eval.cpp
    src/utils.cpp
)

# Generate individual puzzle tests from shared puzzles.json
set(PUZZLES_JSON "${CMAKE_SOURCE_DIR}/../../tests/puzzles.json")
find_program(PYTHON3_EXE NAMES python3 python)
if(PYTHON3_EXE AND EXISTS "${PUZZLES_JSON}")
    execute_process(
        COMMAND ${PYTHON3_EXE} "${CMAKE_SOURCE_DIR}/../../tests/gen_cmake_tests.py"
                               "${PUZZLES_JSON}"
                               "${CMAKE_CURRENT_BINARY_DIR}/puzzle_tests.cmake"
        RESULT_VARIABLE _gen_result
    )
    if(_gen_result EQUAL 0)
        include("${CMAKE_CURRENT_BINARY_DIR}/puzzle_tests.cmake")
    else()
        message(WARNING "Failed to generate puzzle tests from ${PUZZLES_JSON}")
    endif()
else()
    message(WARNING "Python3 or puzzles.json not found; skipping puzzle tests")
endif()

target_compile_definitions(omble_cavalier++ PRIVATE
    "PUZZLES_JSON_PATH=\"${PUZZLES_JSON}\"")
add_test(NAME testDoubledPawnsWhite COMMAND test_pawnstructure testDoubledPawnsWhite)
add_test(NAME testDoubledPawnsBlack COMMAND test_pawnstructure testDoubledPawnsBlack)
add_test(NAME testIsolatedPawnsWhite COMMAND test_pawnstructure testIsolatedPawnsWhite)
add_test(NAME testIsolatedPawnsBlack COMMAND test_pawnstructure testIsolatedPawnsBlack)
add_test(NAME testPassedPawnsWhite COMMAND test_pawnstructure testPassedPawnsWhite)
add_test(NAME testPassedPawnsBlack COMMAND test_pawnstructure testPassedPawnsBlack)
add_test(NAME testPassedPawnsBlackBlockedbyKnight COMMAND test_pawnstructure testPassedPawnsBlackBlockedbyKnight)
add_test(NAME testRookOpenFile COMMAND test_pawnstructure testRookOpenFile)
add_test(NAME testRookSemiOpenFile COMMAND test_pawnstructure testRookSemiOpenFile)
add_test(NAME testRookBlockedByOwnPawn COMMAND test_pawnstructure testRookBlockedByOwnPawn)
add_test(NAME testTwoRooksOpenFiles COMMAND test_pawnstructure testTwoRooksOpenFiles)


# Run all tests at once
add_custom_target(run_all_tests
    COMMAND ${CMAKE_CTEST_COMMAND} --output-on-failure
    DEPENDS omble_cavalier++
)