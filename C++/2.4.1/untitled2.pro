QT += network concurrent widgets sql

CONFIG += c++17

SOURCES += \
    main.cpp \
    mainwindow.cpp

HEADERS += \
    mainwindow.h

# 添加资源文件
RESOURCES += resources.qrc

# 添加版本信息
VERSION = 2.4.1

win32 {
    LIBS += -ladvapi32 -luser32 -lshell32 -lkernel32 -lole32 -lws2_32

DEPLOYMENT += 7z
7z.path = $$OUT_PWD
7z.files = $$PWD/7z/*
INSTALLS += 7z

    # 生成资源文件
    RC_FILE = launcher.rc
}
