cmake_minimum_required(VERSION 2.8.3)
project(system_monitor)

find_package(catkin)

catkin_package()

file(GLOB sources RELATIVE ${PROJECT_SOURCE_DIR} ./bin/*.py)
install(PROGRAMS
  ${sources}
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

install(DIRECTORY config/
        DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}/config
        PATTERN ".svn" EXCLUDE
)

install(DIRECTORY launch/
        DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}/launch
        PATTERN ".svn" EXCLUDE
)
