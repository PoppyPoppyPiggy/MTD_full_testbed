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
include src/point-to-point/examples/CMakeFiles/main-attribute-value.dir/depend.make
# Include any dependencies generated by the compiler for this target.
include src/point-to-point/examples/CMakeFiles/main-attribute-value.dir/compiler_depend.make

# Include the progress variables for this target.
include src/point-to-point/examples/CMakeFiles/main-attribute-value.dir/progress.make

# Include the compile flags for this target's objects.
include src/point-to-point/examples/CMakeFiles/main-attribute-value.dir/flags.make

src/point-to-point/examples/CMakeFiles/main-attribute-value.dir/codegen:
.PHONY : src/point-to-point/examples/CMakeFiles/main-attribute-value.dir/codegen

src/point-to-point/examples/CMakeFiles/main-attribute-value.dir/main-attribute-value.cc.o: src/point-to-point/examples/CMakeFiles/main-attribute-value.dir/flags.make
src/point-to-point/examples/CMakeFiles/main-attribute-value.dir/main-attribute-value.cc.o: /home/kali/MTD/ns-3.45/src/point-to-point/examples/main-attribute-value.cc
src/point-to-point/examples/CMakeFiles/main-attribute-value.dir/main-attribute-value.cc.o: src/point-to-point/examples/CMakeFiles/main-attribute-value.dir/compiler_depend.ts
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green --progress-dir=/home/kali/MTD/ns-3.45/cmake-cache/CMakeFiles --progress-num=$(CMAKE_PROGRESS_1) "Building CXX object src/point-to-point/examples/CMakeFiles/main-attribute-value.dir/main-attribute-value.cc.o"
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/point-to-point/examples && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -MD -MT src/point-to-point/examples/CMakeFiles/main-attribute-value.dir/main-attribute-value.cc.o -MF CMakeFiles/main-attribute-value.dir/main-attribute-value.cc.o.d -o CMakeFiles/main-attribute-value.dir/main-attribute-value.cc.o -c /home/kali/MTD/ns-3.45/src/point-to-point/examples/main-attribute-value.cc

src/point-to-point/examples/CMakeFiles/main-attribute-value.dir/main-attribute-value.cc.i: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green "Preprocessing CXX source to CMakeFiles/main-attribute-value.dir/main-attribute-value.cc.i"
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/point-to-point/examples && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -E /home/kali/MTD/ns-3.45/src/point-to-point/examples/main-attribute-value.cc > CMakeFiles/main-attribute-value.dir/main-attribute-value.cc.i

src/point-to-point/examples/CMakeFiles/main-attribute-value.dir/main-attribute-value.cc.s: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green "Compiling CXX source to assembly CMakeFiles/main-attribute-value.dir/main-attribute-value.cc.s"
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/point-to-point/examples && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -S /home/kali/MTD/ns-3.45/src/point-to-point/examples/main-attribute-value.cc -o CMakeFiles/main-attribute-value.dir/main-attribute-value.cc.s

# Object files for target main-attribute-value
main__attribute__value_OBJECTS = \
"CMakeFiles/main-attribute-value.dir/main-attribute-value.cc.o"

# External object files for target main-attribute-value
main__attribute__value_EXTERNAL_OBJECTS =

/home/kali/MTD/ns-3.45/build/src/point-to-point/examples/ns3.45-main-attribute-value-default: src/point-to-point/examples/CMakeFiles/main-attribute-value.dir/main-attribute-value.cc.o
/home/kali/MTD/ns-3.45/build/src/point-to-point/examples/ns3.45-main-attribute-value-default: src/point-to-point/examples/CMakeFiles/main-attribute-value.dir/build.make
/home/kali/MTD/ns-3.45/build/src/point-to-point/examples/ns3.45-main-attribute-value-default: /usr/lib/x86_64-linux-gnu/libgsl.so
/home/kali/MTD/ns-3.45/build/src/point-to-point/examples/ns3.45-main-attribute-value-default: /usr/lib/x86_64-linux-gnu/libgslcblas.so
/home/kali/MTD/ns-3.45/build/src/point-to-point/examples/ns3.45-main-attribute-value-default: src/point-to-point/examples/CMakeFiles/main-attribute-value.dir/link.txt
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green --bold --progress-dir=/home/kali/MTD/ns-3.45/cmake-cache/CMakeFiles --progress-num=$(CMAKE_PROGRESS_2) "Linking CXX executable /home/kali/MTD/ns-3.45/build/src/point-to-point/examples/ns3.45-main-attribute-value-default"
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/point-to-point/examples && $(CMAKE_COMMAND) -E cmake_link_script CMakeFiles/main-attribute-value.dir/link.txt --verbose=$(VERBOSE)

# Rule to build all files generated by this target.
src/point-to-point/examples/CMakeFiles/main-attribute-value.dir/build: /home/kali/MTD/ns-3.45/build/src/point-to-point/examples/ns3.45-main-attribute-value-default
.PHONY : src/point-to-point/examples/CMakeFiles/main-attribute-value.dir/build

src/point-to-point/examples/CMakeFiles/main-attribute-value.dir/clean:
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/point-to-point/examples && $(CMAKE_COMMAND) -P CMakeFiles/main-attribute-value.dir/cmake_clean.cmake
.PHONY : src/point-to-point/examples/CMakeFiles/main-attribute-value.dir/clean

src/point-to-point/examples/CMakeFiles/main-attribute-value.dir/depend:
	cd /home/kali/MTD/ns-3.45/cmake-cache && $(CMAKE_COMMAND) -E cmake_depends "Unix Makefiles" /home/kali/MTD/ns-3.45 /home/kali/MTD/ns-3.45/src/point-to-point/examples /home/kali/MTD/ns-3.45/cmake-cache /home/kali/MTD/ns-3.45/cmake-cache/src/point-to-point/examples /home/kali/MTD/ns-3.45/cmake-cache/src/point-to-point/examples/CMakeFiles/main-attribute-value.dir/DependInfo.cmake "--color=$(COLOR)"
.PHONY : src/point-to-point/examples/CMakeFiles/main-attribute-value.dir/depend

