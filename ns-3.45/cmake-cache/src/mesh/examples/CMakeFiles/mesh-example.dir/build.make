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
include src/mesh/examples/CMakeFiles/mesh-example.dir/depend.make
# Include any dependencies generated by the compiler for this target.
include src/mesh/examples/CMakeFiles/mesh-example.dir/compiler_depend.make

# Include the progress variables for this target.
include src/mesh/examples/CMakeFiles/mesh-example.dir/progress.make

# Include the compile flags for this target's objects.
include src/mesh/examples/CMakeFiles/mesh-example.dir/flags.make

src/mesh/examples/CMakeFiles/mesh-example.dir/codegen:
.PHONY : src/mesh/examples/CMakeFiles/mesh-example.dir/codegen

src/mesh/examples/CMakeFiles/mesh-example.dir/mesh-example.cc.o: src/mesh/examples/CMakeFiles/mesh-example.dir/flags.make
src/mesh/examples/CMakeFiles/mesh-example.dir/mesh-example.cc.o: /home/kali/MTD/ns-3.45/src/mesh/examples/mesh-example.cc
src/mesh/examples/CMakeFiles/mesh-example.dir/mesh-example.cc.o: src/mesh/examples/CMakeFiles/mesh-example.dir/compiler_depend.ts
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green --progress-dir=/home/kali/MTD/ns-3.45/cmake-cache/CMakeFiles --progress-num=$(CMAKE_PROGRESS_1) "Building CXX object src/mesh/examples/CMakeFiles/mesh-example.dir/mesh-example.cc.o"
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/mesh/examples && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -MD -MT src/mesh/examples/CMakeFiles/mesh-example.dir/mesh-example.cc.o -MF CMakeFiles/mesh-example.dir/mesh-example.cc.o.d -o CMakeFiles/mesh-example.dir/mesh-example.cc.o -c /home/kali/MTD/ns-3.45/src/mesh/examples/mesh-example.cc

src/mesh/examples/CMakeFiles/mesh-example.dir/mesh-example.cc.i: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green "Preprocessing CXX source to CMakeFiles/mesh-example.dir/mesh-example.cc.i"
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/mesh/examples && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -E /home/kali/MTD/ns-3.45/src/mesh/examples/mesh-example.cc > CMakeFiles/mesh-example.dir/mesh-example.cc.i

src/mesh/examples/CMakeFiles/mesh-example.dir/mesh-example.cc.s: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green "Compiling CXX source to assembly CMakeFiles/mesh-example.dir/mesh-example.cc.s"
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/mesh/examples && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -S /home/kali/MTD/ns-3.45/src/mesh/examples/mesh-example.cc -o CMakeFiles/mesh-example.dir/mesh-example.cc.s

# Object files for target mesh-example
mesh__example_OBJECTS = \
"CMakeFiles/mesh-example.dir/mesh-example.cc.o"

# External object files for target mesh-example
mesh__example_EXTERNAL_OBJECTS =

/home/kali/MTD/ns-3.45/build/src/mesh/examples/ns3.45-mesh-example-default: src/mesh/examples/CMakeFiles/mesh-example.dir/mesh-example.cc.o
/home/kali/MTD/ns-3.45/build/src/mesh/examples/ns3.45-mesh-example-default: src/mesh/examples/CMakeFiles/mesh-example.dir/build.make
/home/kali/MTD/ns-3.45/build/src/mesh/examples/ns3.45-mesh-example-default: /usr/lib/x86_64-linux-gnu/libgsl.so
/home/kali/MTD/ns-3.45/build/src/mesh/examples/ns3.45-mesh-example-default: /usr/lib/x86_64-linux-gnu/libgslcblas.so
/home/kali/MTD/ns-3.45/build/src/mesh/examples/ns3.45-mesh-example-default: src/mesh/examples/CMakeFiles/mesh-example.dir/link.txt
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green --bold --progress-dir=/home/kali/MTD/ns-3.45/cmake-cache/CMakeFiles --progress-num=$(CMAKE_PROGRESS_2) "Linking CXX executable /home/kali/MTD/ns-3.45/build/src/mesh/examples/ns3.45-mesh-example-default"
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/mesh/examples && $(CMAKE_COMMAND) -E cmake_link_script CMakeFiles/mesh-example.dir/link.txt --verbose=$(VERBOSE)

# Rule to build all files generated by this target.
src/mesh/examples/CMakeFiles/mesh-example.dir/build: /home/kali/MTD/ns-3.45/build/src/mesh/examples/ns3.45-mesh-example-default
.PHONY : src/mesh/examples/CMakeFiles/mesh-example.dir/build

src/mesh/examples/CMakeFiles/mesh-example.dir/clean:
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/mesh/examples && $(CMAKE_COMMAND) -P CMakeFiles/mesh-example.dir/cmake_clean.cmake
.PHONY : src/mesh/examples/CMakeFiles/mesh-example.dir/clean

src/mesh/examples/CMakeFiles/mesh-example.dir/depend:
	cd /home/kali/MTD/ns-3.45/cmake-cache && $(CMAKE_COMMAND) -E cmake_depends "Unix Makefiles" /home/kali/MTD/ns-3.45 /home/kali/MTD/ns-3.45/src/mesh/examples /home/kali/MTD/ns-3.45/cmake-cache /home/kali/MTD/ns-3.45/cmake-cache/src/mesh/examples /home/kali/MTD/ns-3.45/cmake-cache/src/mesh/examples/CMakeFiles/mesh-example.dir/DependInfo.cmake "--color=$(COLOR)"
.PHONY : src/mesh/examples/CMakeFiles/mesh-example.dir/depend

