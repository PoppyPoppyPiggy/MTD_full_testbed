# Install script for directory: /home/kali/MTD/ns-3.45/src/applications

# Set the install prefix
if(NOT DEFINED CMAKE_INSTALL_PREFIX)
  set(CMAKE_INSTALL_PREFIX "/usr/local")
endif()
string(REGEX REPLACE "/$" "" CMAKE_INSTALL_PREFIX "${CMAKE_INSTALL_PREFIX}")

# Set the install configuration name.
if(NOT DEFINED CMAKE_INSTALL_CONFIG_NAME)
  if(BUILD_TYPE)
    string(REGEX REPLACE "^[^A-Za-z0-9_]+" ""
           CMAKE_INSTALL_CONFIG_NAME "${BUILD_TYPE}")
  else()
    set(CMAKE_INSTALL_CONFIG_NAME "default")
  endif()
  message(STATUS "Install configuration: \"${CMAKE_INSTALL_CONFIG_NAME}\"")
endif()

# Set the component getting installed.
if(NOT CMAKE_INSTALL_COMPONENT)
  if(COMPONENT)
    message(STATUS "Install component: \"${COMPONENT}\"")
    set(CMAKE_INSTALL_COMPONENT "${COMPONENT}")
  else()
    set(CMAKE_INSTALL_COMPONENT)
  endif()
endif()

# Install shared libraries without execute permission?
if(NOT DEFINED CMAKE_INSTALL_SO_NO_EXE)
  set(CMAKE_INSTALL_SO_NO_EXE "1")
endif()

# Is this installation the result of a crosscompile?
if(NOT DEFINED CMAKE_CROSSCOMPILING)
  set(CMAKE_CROSSCOMPILING "FALSE")
endif()

# Set path to fallback-tool for dependency-resolution.
if(NOT DEFINED CMAKE_OBJDUMP)
  set(CMAKE_OBJDUMP "/usr/bin/objdump")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
  if(EXISTS "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libns3.45-applications-default.so" AND
     NOT IS_SYMLINK "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libns3.45-applications-default.so")
    file(RPATH_CHECK
         FILE "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libns3.45-applications-default.so"
         RPATH "/usr/local/lib:$ORIGIN/:$ORIGIN/../lib:/usr/local/lib64:$ORIGIN/:$ORIGIN/../lib64")
  endif()
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib" TYPE SHARED_LIBRARY FILES "/home/kali/MTD/ns-3.45/build/lib/libns3.45-applications-default.so")
  if(EXISTS "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libns3.45-applications-default.so" AND
     NOT IS_SYMLINK "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libns3.45-applications-default.so")
    file(RPATH_CHANGE
         FILE "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libns3.45-applications-default.so"
         OLD_RPATH "/home/kali/MTD/ns-3.45/build/lib:::::::::::::::::::::::::::::::::::::::::::::::::"
         NEW_RPATH "/usr/local/lib:$ORIGIN/:$ORIGIN/../lib:/usr/local/lib64:$ORIGIN/:$ORIGIN/../lib64")
    if(CMAKE_INSTALL_DO_STRIP)
      execute_process(COMMAND "/usr/bin/strip" "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libns3.45-applications-default.so")
    endif()
  endif()
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/include/ns3" TYPE FILE FILES
    "/home/kali/MTD/ns-3.45/src/applications/helper/bulk-send-helper.h"
    "/home/kali/MTD/ns-3.45/src/applications/helper/on-off-helper.h"
    "/home/kali/MTD/ns-3.45/src/applications/helper/packet-sink-helper.h"
    "/home/kali/MTD/ns-3.45/src/applications/helper/three-gpp-http-helper.h"
    "/home/kali/MTD/ns-3.45/src/applications/helper/udp-client-server-helper.h"
    "/home/kali/MTD/ns-3.45/src/applications/helper/udp-echo-helper.h"
    "/home/kali/MTD/ns-3.45/src/applications/model/application-packet-probe.h"
    "/home/kali/MTD/ns-3.45/src/applications/model/bulk-send-application.h"
    "/home/kali/MTD/ns-3.45/src/applications/model/onoff-application.h"
    "/home/kali/MTD/ns-3.45/src/applications/model/packet-loss-counter.h"
    "/home/kali/MTD/ns-3.45/src/applications/model/packet-sink.h"
    "/home/kali/MTD/ns-3.45/src/applications/model/seq-ts-echo-header.h"
    "/home/kali/MTD/ns-3.45/src/applications/model/seq-ts-header.h"
    "/home/kali/MTD/ns-3.45/src/applications/model/seq-ts-size-header.h"
    "/home/kali/MTD/ns-3.45/src/applications/model/sink-application.h"
    "/home/kali/MTD/ns-3.45/src/applications/model/source-application.h"
    "/home/kali/MTD/ns-3.45/src/applications/model/three-gpp-http-client.h"
    "/home/kali/MTD/ns-3.45/src/applications/model/three-gpp-http-header.h"
    "/home/kali/MTD/ns-3.45/src/applications/model/three-gpp-http-server.h"
    "/home/kali/MTD/ns-3.45/src/applications/model/three-gpp-http-variables.h"
    "/home/kali/MTD/ns-3.45/src/applications/model/udp-client.h"
    "/home/kali/MTD/ns-3.45/src/applications/model/udp-echo-client.h"
    "/home/kali/MTD/ns-3.45/src/applications/model/udp-echo-server.h"
    "/home/kali/MTD/ns-3.45/src/applications/model/udp-server.h"
    "/home/kali/MTD/ns-3.45/src/applications/model/udp-trace-client.h"
    "/home/kali/MTD/ns-3.45/build/include/ns3/applications-module.h"
    )
endif()

if(NOT CMAKE_INSTALL_LOCAL_ONLY)
  # Include the install script for each subdirectory.
  include("/home/kali/MTD/ns-3.45/cmake-cache/src/applications/examples/cmake_install.cmake")

endif()

string(REPLACE ";" "\n" CMAKE_INSTALL_MANIFEST_CONTENT
       "${CMAKE_INSTALL_MANIFEST_FILES}")
if(CMAKE_INSTALL_LOCAL_ONLY)
  file(WRITE "/home/kali/MTD/ns-3.45/cmake-cache/src/applications/install_local_manifest.txt"
     "${CMAKE_INSTALL_MANIFEST_CONTENT}")
endif()
