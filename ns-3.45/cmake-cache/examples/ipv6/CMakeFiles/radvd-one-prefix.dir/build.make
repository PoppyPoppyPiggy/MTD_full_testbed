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
include examples/ipv6/CMakeFiles/radvd-one-prefix.dir/depend.make
# Include any dependencies generated by the compiler for this target.
include examples/ipv6/CMakeFiles/radvd-one-prefix.dir/compiler_depend.make

# Include the progress variables for this target.
include examples/ipv6/CMakeFiles/radvd-one-prefix.dir/progress.make

# Include the compile flags for this target's objects.
include examples/ipv6/CMakeFiles/radvd-one-prefix.dir/flags.make

examples/ipv6/CMakeFiles/radvd-one-prefix.dir/codegen:
.PHONY : examples/ipv6/CMakeFiles/radvd-one-prefix.dir/codegen

examples/ipv6/CMakeFiles/radvd-one-prefix.dir/radvd-one-prefix.cc.o: examples/ipv6/CMakeFiles/radvd-one-prefix.dir/flags.make
examples/ipv6/CMakeFiles/radvd-one-prefix.dir/radvd-one-prefix.cc.o: /home/kali/MTD/ns-3.45/examples/ipv6/radvd-one-prefix.cc
examples/ipv6/CMakeFiles/radvd-one-prefix.dir/radvd-one-prefix.cc.o: examples/ipv6/CMakeFiles/radvd-one-prefix.dir/compiler_depend.ts
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green --progress-dir=/home/kali/MTD/ns-3.45/cmake-cache/CMakeFiles --progress-num=$(CMAKE_PROGRESS_1) "Building CXX object examples/ipv6/CMakeFiles/radvd-one-prefix.dir/radvd-one-prefix.cc.o"
	cd /home/kali/MTD/ns-3.45/cmake-cache/examples/ipv6 && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -MD -MT examples/ipv6/CMakeFiles/radvd-one-prefix.dir/radvd-one-prefix.cc.o -MF CMakeFiles/radvd-one-prefix.dir/radvd-one-prefix.cc.o.d -o CMakeFiles/radvd-one-prefix.dir/radvd-one-prefix.cc.o -c /home/kali/MTD/ns-3.45/examples/ipv6/radvd-one-prefix.cc

examples/ipv6/CMakeFiles/radvd-one-prefix.dir/radvd-one-prefix.cc.i: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green "Preprocessing CXX source to CMakeFiles/radvd-one-prefix.dir/radvd-one-prefix.cc.i"
	cd /home/kali/MTD/ns-3.45/cmake-cache/examples/ipv6 && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -E /home/kali/MTD/ns-3.45/examples/ipv6/radvd-one-prefix.cc > CMakeFiles/radvd-one-prefix.dir/radvd-one-prefix.cc.i

examples/ipv6/CMakeFiles/radvd-one-prefix.dir/radvd-one-prefix.cc.s: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green "Compiling CXX source to assembly CMakeFiles/radvd-one-prefix.dir/radvd-one-prefix.cc.s"
	cd /home/kali/MTD/ns-3.45/cmake-cache/examples/ipv6 && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -S /home/kali/MTD/ns-3.45/examples/ipv6/radvd-one-prefix.cc -o CMakeFiles/radvd-one-prefix.dir/radvd-one-prefix.cc.s

# Object files for target radvd-one-prefix
radvd__one__prefix_OBJECTS = \
"CMakeFiles/radvd-one-prefix.dir/radvd-one-prefix.cc.o"

# External object files for target radvd-one-prefix
radvd__one__prefix_EXTERNAL_OBJECTS =

/home/kali/MTD/ns-3.45/build/examples/ipv6/ns3.45-radvd-one-prefix-default: examples/ipv6/CMakeFiles/radvd-one-prefix.dir/radvd-one-prefix.cc.o
/home/kali/MTD/ns-3.45/build/examples/ipv6/ns3.45-radvd-one-prefix-default: examples/ipv6/CMakeFiles/radvd-one-prefix.dir/build.make
/home/kali/MTD/ns-3.45/build/examples/ipv6/ns3.45-radvd-one-prefix-default: /usr/lib/x86_64-linux-gnu/libgsl.so
/home/kali/MTD/ns-3.45/build/examples/ipv6/ns3.45-radvd-one-prefix-default: /usr/lib/x86_64-linux-gnu/libgslcblas.so
/home/kali/MTD/ns-3.45/build/examples/ipv6/ns3.45-radvd-one-prefix-default: examples/ipv6/CMakeFiles/radvd-one-prefix.dir/link.txt
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green --bold --progress-dir=/home/kali/MTD/ns-3.45/cmake-cache/CMakeFiles --progress-num=$(CMAKE_PROGRESS_2) "Linking CXX executable /home/kali/MTD/ns-3.45/build/examples/ipv6/ns3.45-radvd-one-prefix-default"
	cd /home/kali/MTD/ns-3.45/cmake-cache/examples/ipv6 && $(CMAKE_COMMAND) -E cmake_link_script CMakeFiles/radvd-one-prefix.dir/link.txt --verbose=$(VERBOSE)

# Rule to build all files generated by this target.
examples/ipv6/CMakeFiles/radvd-one-prefix.dir/build: /home/kali/MTD/ns-3.45/build/examples/ipv6/ns3.45-radvd-one-prefix-default
.PHONY : examples/ipv6/CMakeFiles/radvd-one-prefix.dir/build

examples/ipv6/CMakeFiles/radvd-one-prefix.dir/clean:
	cd /home/kali/MTD/ns-3.45/cmake-cache/examples/ipv6 && $(CMAKE_COMMAND) -P CMakeFiles/radvd-one-prefix.dir/cmake_clean.cmake
.PHONY : examples/ipv6/CMakeFiles/radvd-one-prefix.dir/clean

examples/ipv6/CMakeFiles/radvd-one-prefix.dir/depend:
	cd /home/kali/MTD/ns-3.45/cmake-cache && $(CMAKE_COMMAND) -E cmake_depends "Unix Makefiles" /home/kali/MTD/ns-3.45 /home/kali/MTD/ns-3.45/examples/ipv6 /home/kali/MTD/ns-3.45/cmake-cache /home/kali/MTD/ns-3.45/cmake-cache/examples/ipv6 /home/kali/MTD/ns-3.45/cmake-cache/examples/ipv6/CMakeFiles/radvd-one-prefix.dir/DependInfo.cmake "--color=$(COLOR)"
.PHONY : examples/ipv6/CMakeFiles/radvd-one-prefix.dir/depend

