# CMAKE generated file: DO NOT EDIT!
# Generated by "Unix Makefiles" Generator, CMake Version 3.31

# Delete rule output on recipe failure.
.DELETE_ON_ERROR:

#=============================================================================
# Special targets provided by cmake.

# Disable implicit rules so canonical targets will work.
.SUFFIXES:

# Disable VCS-based implicit rules.
% : %,v

# Disable VCS-based implicit rules.
% : RCS/%

# Disable VCS-based implicit rules.
% : RCS/%,v

# Disable VCS-based implicit rules.
% : SCCS/s.%

# Disable VCS-based implicit rules.
% : s.%

.SUFFIXES: .hpux_make_needs_suffix_list

# Command-line flag to silence nested $(MAKE).
$(VERBOSE)MAKESILENT = -s

#Suppress display of executed commands.
$(VERBOSE).SILENT:

# A target that is always out of date.
cmake_force:
.PHONY : cmake_force

#=============================================================================
# Set environment variables for the build.

# The shell in which to execute make rules.
SHELL = /bin/sh

# The CMake executable.
CMAKE_COMMAND = /usr/bin/cmake

# The command to remove a file.
RM = /usr/bin/cmake -E rm -f

# Escaping for special characters.
EQUALS = =

# The top-level source directory on which CMake was run.
CMAKE_SOURCE_DIR = /home/kali/MTD/ns-3.45

# The top-level build directory on which CMake was run.
CMAKE_BINARY_DIR = /home/kali/MTD/ns-3.45/cmake-cache

# Include any dependencies generated for this target.
include src/nix-vector-routing/CMakeFiles/nix-vector-routing-test.dir/depend.make
# Include any dependencies generated by the compiler for this target.
include src/nix-vector-routing/CMakeFiles/nix-vector-routing-test.dir/compiler_depend.make

# Include the progress variables for this target.
include src/nix-vector-routing/CMakeFiles/nix-vector-routing-test.dir/progress.make

# Include the compile flags for this target's objects.
include src/nix-vector-routing/CMakeFiles/nix-vector-routing-test.dir/flags.make

src/nix-vector-routing/CMakeFiles/nix-vector-routing-test.dir/codegen:
.PHONY : src/nix-vector-routing/CMakeFiles/nix-vector-routing-test.dir/codegen

src/nix-vector-routing/CMakeFiles/nix-vector-routing-test.dir/test/nix-test.cc.o: src/nix-vector-routing/CMakeFiles/nix-vector-routing-test.dir/flags.make
src/nix-vector-routing/CMakeFiles/nix-vector-routing-test.dir/test/nix-test.cc.o: /home/kali/MTD/ns-3.45/src/nix-vector-routing/test/nix-test.cc
src/nix-vector-routing/CMakeFiles/nix-vector-routing-test.dir/test/nix-test.cc.o: src/nix-vector-routing/CMakeFiles/nix-vector-routing-test.dir/compiler_depend.ts
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green --progress-dir=/home/kali/MTD/ns-3.45/cmake-cache/CMakeFiles --progress-num=$(CMAKE_PROGRESS_1) "Building CXX object src/nix-vector-routing/CMakeFiles/nix-vector-routing-test.dir/test/nix-test.cc.o"
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/nix-vector-routing && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -MD -MT src/nix-vector-routing/CMakeFiles/nix-vector-routing-test.dir/test/nix-test.cc.o -MF CMakeFiles/nix-vector-routing-test.dir/test/nix-test.cc.o.d -o CMakeFiles/nix-vector-routing-test.dir/test/nix-test.cc.o -c /home/kali/MTD/ns-3.45/src/nix-vector-routing/test/nix-test.cc

src/nix-vector-routing/CMakeFiles/nix-vector-routing-test.dir/test/nix-test.cc.i: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green "Preprocessing CXX source to CMakeFiles/nix-vector-routing-test.dir/test/nix-test.cc.i"
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/nix-vector-routing && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -E /home/kali/MTD/ns-3.45/src/nix-vector-routing/test/nix-test.cc > CMakeFiles/nix-vector-routing-test.dir/test/nix-test.cc.i

src/nix-vector-routing/CMakeFiles/nix-vector-routing-test.dir/test/nix-test.cc.s: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green "Compiling CXX source to assembly CMakeFiles/nix-vector-routing-test.dir/test/nix-test.cc.s"
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/nix-vector-routing && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -S /home/kali/MTD/ns-3.45/src/nix-vector-routing/test/nix-test.cc -o CMakeFiles/nix-vector-routing-test.dir/test/nix-test.cc.s

# Object files for target nix-vector-routing-test
nix__vector__routing__test_OBJECTS = \
"CMakeFiles/nix-vector-routing-test.dir/test/nix-test.cc.o"

# External object files for target nix-vector-routing-test
nix__vector__routing__test_EXTERNAL_OBJECTS =

/home/kali/MTD/ns-3.45/build/lib/libns3.45-nix-vector-routing-test-default.so: src/nix-vector-routing/CMakeFiles/nix-vector-routing-test.dir/test/nix-test.cc.o
/home/kali/MTD/ns-3.45/build/lib/libns3.45-nix-vector-routing-test-default.so: src/nix-vector-routing/CMakeFiles/nix-vector-routing-test.dir/build.make
/home/kali/MTD/ns-3.45/build/lib/libns3.45-nix-vector-routing-test-default.so: /usr/lib/x86_64-linux-gnu/libgsl.so
/home/kali/MTD/ns-3.45/build/lib/libns3.45-nix-vector-routing-test-default.so: /usr/lib/x86_64-linux-gnu/libgslcblas.so
/home/kali/MTD/ns-3.45/build/lib/libns3.45-nix-vector-routing-test-default.so: src/nix-vector-routing/CMakeFiles/nix-vector-routing-test.dir/link.txt
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green --bold --progress-dir=/home/kali/MTD/ns-3.45/cmake-cache/CMakeFiles --progress-num=$(CMAKE_PROGRESS_2) "Linking CXX shared library /home/kali/MTD/ns-3.45/build/lib/libns3.45-nix-vector-routing-test-default.so"
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/nix-vector-routing && $(CMAKE_COMMAND) -E cmake_link_script CMakeFiles/nix-vector-routing-test.dir/link.txt --verbose=$(VERBOSE)

# Rule to build all files generated by this target.
src/nix-vector-routing/CMakeFiles/nix-vector-routing-test.dir/build: /home/kali/MTD/ns-3.45/build/lib/libns3.45-nix-vector-routing-test-default.so
.PHONY : src/nix-vector-routing/CMakeFiles/nix-vector-routing-test.dir/build

src/nix-vector-routing/CMakeFiles/nix-vector-routing-test.dir/clean:
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/nix-vector-routing && $(CMAKE_COMMAND) -P CMakeFiles/nix-vector-routing-test.dir/cmake_clean.cmake
.PHONY : src/nix-vector-routing/CMakeFiles/nix-vector-routing-test.dir/clean

src/nix-vector-routing/CMakeFiles/nix-vector-routing-test.dir/depend:
	cd /home/kali/MTD/ns-3.45/cmake-cache && $(CMAKE_COMMAND) -E cmake_depends "Unix Makefiles" /home/kali/MTD/ns-3.45 /home/kali/MTD/ns-3.45/src/nix-vector-routing /home/kali/MTD/ns-3.45/cmake-cache /home/kali/MTD/ns-3.45/cmake-cache/src/nix-vector-routing /home/kali/MTD/ns-3.45/cmake-cache/src/nix-vector-routing/CMakeFiles/nix-vector-routing-test.dir/DependInfo.cmake "--color=$(COLOR)"
.PHONY : src/nix-vector-routing/CMakeFiles/nix-vector-routing-test.dir/depend

