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
include src/spectrum/examples/CMakeFiles/tv-trans-regional-example.dir/depend.make
# Include any dependencies generated by the compiler for this target.
include src/spectrum/examples/CMakeFiles/tv-trans-regional-example.dir/compiler_depend.make

# Include the progress variables for this target.
include src/spectrum/examples/CMakeFiles/tv-trans-regional-example.dir/progress.make

# Include the compile flags for this target's objects.
include src/spectrum/examples/CMakeFiles/tv-trans-regional-example.dir/flags.make

src/spectrum/examples/CMakeFiles/tv-trans-regional-example.dir/codegen:
.PHONY : src/spectrum/examples/CMakeFiles/tv-trans-regional-example.dir/codegen

src/spectrum/examples/CMakeFiles/tv-trans-regional-example.dir/tv-trans-regional-example.cc.o: src/spectrum/examples/CMakeFiles/tv-trans-regional-example.dir/flags.make
src/spectrum/examples/CMakeFiles/tv-trans-regional-example.dir/tv-trans-regional-example.cc.o: /home/kali/MTD/ns-3.45/src/spectrum/examples/tv-trans-regional-example.cc
src/spectrum/examples/CMakeFiles/tv-trans-regional-example.dir/tv-trans-regional-example.cc.o: src/spectrum/examples/CMakeFiles/tv-trans-regional-example.dir/compiler_depend.ts
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green --progress-dir=/home/kali/MTD/ns-3.45/cmake-cache/CMakeFiles --progress-num=$(CMAKE_PROGRESS_1) "Building CXX object src/spectrum/examples/CMakeFiles/tv-trans-regional-example.dir/tv-trans-regional-example.cc.o"
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/spectrum/examples && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -MD -MT src/spectrum/examples/CMakeFiles/tv-trans-regional-example.dir/tv-trans-regional-example.cc.o -MF CMakeFiles/tv-trans-regional-example.dir/tv-trans-regional-example.cc.o.d -o CMakeFiles/tv-trans-regional-example.dir/tv-trans-regional-example.cc.o -c /home/kali/MTD/ns-3.45/src/spectrum/examples/tv-trans-regional-example.cc

src/spectrum/examples/CMakeFiles/tv-trans-regional-example.dir/tv-trans-regional-example.cc.i: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green "Preprocessing CXX source to CMakeFiles/tv-trans-regional-example.dir/tv-trans-regional-example.cc.i"
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/spectrum/examples && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -E /home/kali/MTD/ns-3.45/src/spectrum/examples/tv-trans-regional-example.cc > CMakeFiles/tv-trans-regional-example.dir/tv-trans-regional-example.cc.i

src/spectrum/examples/CMakeFiles/tv-trans-regional-example.dir/tv-trans-regional-example.cc.s: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green "Compiling CXX source to assembly CMakeFiles/tv-trans-regional-example.dir/tv-trans-regional-example.cc.s"
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/spectrum/examples && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -S /home/kali/MTD/ns-3.45/src/spectrum/examples/tv-trans-regional-example.cc -o CMakeFiles/tv-trans-regional-example.dir/tv-trans-regional-example.cc.s

# Object files for target tv-trans-regional-example
tv__trans__regional__example_OBJECTS = \
"CMakeFiles/tv-trans-regional-example.dir/tv-trans-regional-example.cc.o"

# External object files for target tv-trans-regional-example
tv__trans__regional__example_EXTERNAL_OBJECTS =

/home/kali/MTD/ns-3.45/build/src/spectrum/examples/ns3.45-tv-trans-regional-example-default: src/spectrum/examples/CMakeFiles/tv-trans-regional-example.dir/tv-trans-regional-example.cc.o
/home/kali/MTD/ns-3.45/build/src/spectrum/examples/ns3.45-tv-trans-regional-example-default: src/spectrum/examples/CMakeFiles/tv-trans-regional-example.dir/build.make
/home/kali/MTD/ns-3.45/build/src/spectrum/examples/ns3.45-tv-trans-regional-example-default: /usr/lib/x86_64-linux-gnu/libgsl.so
/home/kali/MTD/ns-3.45/build/src/spectrum/examples/ns3.45-tv-trans-regional-example-default: /usr/lib/x86_64-linux-gnu/libgslcblas.so
/home/kali/MTD/ns-3.45/build/src/spectrum/examples/ns3.45-tv-trans-regional-example-default: src/spectrum/examples/CMakeFiles/tv-trans-regional-example.dir/link.txt
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green --bold --progress-dir=/home/kali/MTD/ns-3.45/cmake-cache/CMakeFiles --progress-num=$(CMAKE_PROGRESS_2) "Linking CXX executable /home/kali/MTD/ns-3.45/build/src/spectrum/examples/ns3.45-tv-trans-regional-example-default"
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/spectrum/examples && $(CMAKE_COMMAND) -E cmake_link_script CMakeFiles/tv-trans-regional-example.dir/link.txt --verbose=$(VERBOSE)

# Rule to build all files generated by this target.
src/spectrum/examples/CMakeFiles/tv-trans-regional-example.dir/build: /home/kali/MTD/ns-3.45/build/src/spectrum/examples/ns3.45-tv-trans-regional-example-default
.PHONY : src/spectrum/examples/CMakeFiles/tv-trans-regional-example.dir/build

src/spectrum/examples/CMakeFiles/tv-trans-regional-example.dir/clean:
	cd /home/kali/MTD/ns-3.45/cmake-cache/src/spectrum/examples && $(CMAKE_COMMAND) -P CMakeFiles/tv-trans-regional-example.dir/cmake_clean.cmake
.PHONY : src/spectrum/examples/CMakeFiles/tv-trans-regional-example.dir/clean

src/spectrum/examples/CMakeFiles/tv-trans-regional-example.dir/depend:
	cd /home/kali/MTD/ns-3.45/cmake-cache && $(CMAKE_COMMAND) -E cmake_depends "Unix Makefiles" /home/kali/MTD/ns-3.45 /home/kali/MTD/ns-3.45/src/spectrum/examples /home/kali/MTD/ns-3.45/cmake-cache /home/kali/MTD/ns-3.45/cmake-cache/src/spectrum/examples /home/kali/MTD/ns-3.45/cmake-cache/src/spectrum/examples/CMakeFiles/tv-trans-regional-example.dir/DependInfo.cmake "--color=$(COLOR)"
.PHONY : src/spectrum/examples/CMakeFiles/tv-trans-regional-example.dir/depend

