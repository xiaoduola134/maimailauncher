#include "mainwindow.h"
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QPushButton>
#include <QProgressBar>
#include <QTextEdit>
#include <QLineEdit>
#include <QCheckBox>
#include <QMessageBox>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QJsonDocument>
#include <QJsonArray>
#include <QFile>
#include <QDir>
#include <QProcess>
#include <QDesktopServices>
#include <QUrl>
#include <QSystemTrayIcon>
#include <QMenu>
#include <QCloseEvent>
#include <QThread>
#include <QSslConfiguration>
#include <QSslSocket>
#include <QUuid>
#include <QCryptographicHash>
#include <QDateTime>
#include <QFuture>
#include <QtConcurrent>
#include <QDebug>
#include <QGuiApplication>
#include <QScreen>
#include <QFileDialog>
#include <QTimer>
#include <QUrlQuery>
#include <QRegularExpression>
#include <QButtonGroup>
#include <windows.h>
#include <sddl.h>
#include <winreg.h>
#include <QRadioButton>
#include <QButtonGroup>
#include <QHostInfo> // 添加用于DNS解析的头文件
#include <QElapsedTimer> // 添加用于计时
#include <QStandardPaths>
#include <QDebug>
#include <QSslSocket>
const QString UPDATE_F_VERSION_FILE = "";
const QString DATA_DIR = "";

void ensureDataDirExists()
{

    qDebug()<<QSslSocket::sslLibraryBuildVersionString();
    QString dataDir = "";
    QDir dDrive("");


    if (!dDrive.exists()) {
        dataDir = "";
    }

    QDir dir(dataDir);
    if (!dir.exists()) {
        dir.mkpath(".");
    }

    const wchar_t* path = reinterpret_cast<const wchar_t*>(dataDir.utf16());
    DWORD attributes = GetFileAttributesW(path);
    if (attributes != INVALID_FILE_ATTRIBUTES) {
        SetFileAttributesW(path, attributes | FILE_ATTRIBUTE_HIDDEN);
    }
}


AuthWindow::AuthWindow(const QString &deviceId, const QString &savedKami, QWidget *parent)
    : QDialog(parent)
{
    setWindowTitle("卡密验证");
    setFixedSize(400, 250);
    setWindowModality(Qt::ApplicationModal);

    QVBoxLayout *layout = new QVBoxLayout(this);
    layout->setContentsMargins(20, 20, 20, 20);
    layout->setSpacing(15);

    QLabel *deviceLabel = new QLabel("设备ID: " + deviceId);
    deviceLabel->setStyleSheet("font-size: 10pt;");
    layout->addWidget(deviceLabel);

    QLabel *kamiLabel = new QLabel("卡密:");
    layout->addWidget(kamiLabel);

    kamiEntry = new QLineEdit();
    kamiEntry->setPlaceholderText("请输入您的卡密");
    if (!savedKami.isEmpty()) {
        kamiEntry->setText(savedKami);
    }
    layout->addWidget(kamiEntry);

    rememberCheck = new QCheckBox("记住卡密");
    rememberCheck->setChecked(true);
    layout->addWidget(rememberCheck);

    QHBoxLayout *btnLayout = new QHBoxLayout();
    QPushButton *okBtn = new QPushButton("验证");
    connect(okBtn, &QPushButton::clicked, this, &QDialog::accept);
    btnLayout->addWidget(okBtn);

    QPushButton *cancelBtn = new QPushButton("取消");
    connect(cancelBtn, &QPushButton::clicked, this, &QDialog::reject);
    btnLayout->addWidget(cancelBtn);

    layout->addLayout(btnLayout);
}

QString AuthWindow::getKami() const
{
    return kamiEntry->text().trimmed();
}

bool AuthWindow::getRemember() const
{
    return rememberCheck->isChecked();
}

MainWindow::MainWindow(QWidget *parent)
    : QMainWindow(parent)
    , m_isFirstUpdateInProgress(false) // 先初始化这个
    , gameProcess(nullptr)  // 然后初始化这个
{
    // 检测是否是首次启动
    QDir dataDir(DATA_DIR);
    isFirstLaunch = !dataDir.exists();

    ensureDataDirExists();
    settings = new QSettings("GameStudio", "maimaiLauncher", this);
    loadSettings();

    SERVER_URL = "";
    VERSION_FILE = "";
    UPDATE_ZIP = "";
    ANNOUNCEMENT_FILE = "";
    DEVICE_CODE_FILE = DATA_DIR + "";
    CARD_FILE = DATA_DIR + "";

    deviceId = getDeviceId();
    savedKami = loadSavedKami();

    setupUI();
    checkAdminRights();

        
    nodeMap["node1"] = "";
    nodeMap["node2"] = ""; 
    nodeMap["node3"] = ""; 
    nodeMap["test"] = "";
    testNodePassword = "";
    nodeHostMap["node1"] = "";
    nodeHostMap["node2"] = "";
    nodeHostMap["node3"] = "";
    nodeHostMap["test"] = "";

    // 加载本地版本信息
    loadLocalVersion();

    checkPackageExists();
    disableButtons();

    if (!savedKami.isEmpty()) {
        authStatus->setText("使用保存的卡密验证中...");
        QTimer::singleShot(100, this, [this]() {
            performNetworkAuthentication(savedKami, true);
            checkAndDeleteFiles(); 
        });
    } else {
        authStatus->setText("等待卡密验证");
        QTimer::singleShot(100, this, &MainWindow::showAuthWindow);
    }

    fetchAnnouncement();

    quitTimer = new QTimer(this);
    quitTimer->setSingleShot(true);
    connect(quitTimer, &QTimer::timeout, this, &MainWindow::quitApplication);
}

MainWindow::~MainWindow()
{
    saveSettings();
    delete settings;
    
    // 清理所有ping测试
    for (auto it = pingReplies.begin(); it != pingReplies.end(); ++it) {
        if (it.value()) {
            it.value()->abort();
            it.value()->deleteLater();
        }
    }
    pingReplies.clear();
}

void MainWindow::loadLocalVersion()
{
    QString versionFilePath = UPDATE_PATH + "/" + VERSION_FILE;
    QFile file(versionFilePath);

    if (file.exists() && file.open(QIODevice::ReadOnly)) {
        QByteArray data = file.readAll();
        file.close();

        QJsonDocument doc = QJsonDocument::fromJson(data);
        if (!doc.isNull() && doc.isObject()) {
            localVersion = doc.object();
            QString ver = localVersion["version"].toString();
            versionLabel->setText("版本: v" + ver);
            qDebug() << "加载本地版本: v" << ver;
        } else {
            versionLabel->setText("版本: 文件损坏");
            qDebug() << "版本文件损坏";
        }
    } else {
        // 如果版本文件不存在，创建初始版本
        localVersion = QJsonObject();
        localVersion["version"] = "0.0.0";
        saveLocalVersion();
        versionLabel->setText("版本: 未安装");
        qDebug() << "创建初始版本文件";
    }
}

void MainWindow::setupUI()
{
    setWindowTitle("maimai启动器 v" + LAUNCHER_VERSION);
    setFixedSize(800, 600);

    QWidget *centralWidget = new QWidget(this);
    QVBoxLayout *mainLayout = new QVBoxLayout(centralWidget);

    QWidget *pathWidget = new QWidget();
    QHBoxLayout *pathLayout = new QHBoxLayout(pathWidget);
    pathLayout->setContentsMargins(10, 5, 10, 5);

    QLabel *pathTitle = new QLabel("Package路径:");
    pathLabel = new QLabel(UPDATE_PATH);
    pathLabel->setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc; padding: 3px;");
    pathLabel->setMinimumWidth(300);

    pathSelectBtn = new QPushButton("选择路径");
    pathSelectBtn->setFixedSize(80, 25);
    connect(pathSelectBtn, &QPushButton::clicked, this, &MainWindow::selectPackagePath);

    pathLayout->addWidget(pathTitle);
    pathLayout->addWidget(pathLabel, 1);
    pathLayout->addWidget(pathSelectBtn);

    mainLayout->addWidget(pathWidget);

    QWidget *contentWidget = new QWidget();
    QHBoxLayout *contentLayout = new QHBoxLayout(contentWidget);

    QWidget *leftWidget = new QWidget();
    QVBoxLayout *leftLayout = new QVBoxLayout(leftWidget);
    leftLayout->setContentsMargins(10, 10, 10, 10);

    QLabel *titleLabel = new QLabel("maimai启动器");
    titleLabel->setStyleSheet("font-size: 16pt; font-weight: bold;");
    leftLayout->addWidget(titleLabel, 0, Qt::AlignCenter);

    QLabel *adminLabel = new QLabel("(已获得管理员权限)");
    adminLabel->setStyleSheet("color: green; font-size: 8pt;");
    leftLayout->addWidget(adminLabel, 0, Qt::AlignCenter);

    authStatus = new QLabel("验证状态: 正在初始化...");
    authStatus->setStyleSheet("color: blue; font-weight: bold;");
    leftLayout->addWidget(authStatus, 0, Qt::AlignCenter);

    vipInfo = new QLabel("VIP状态: 未验证");
    vipInfo->setStyleSheet("color: purple;");
    leftLayout->addWidget(vipInfo, 0, Qt::AlignCenter);

    versionLabel = new QLabel("版本: 加载中...");
    leftLayout->addWidget(versionLabel, 0, Qt::AlignCenter);

    progressBar = new QProgressBar();
    progressBar->setFixedHeight(20);
    leftLayout->addWidget(progressBar);

    statusLabel = new QLabel("等待验证...");
    leftLayout->addWidget(statusLabel, 0, Qt::AlignCenter);

    QWidget *buttonWidget = new QWidget();
    QVBoxLayout *buttonLayout = new QVBoxLayout(buttonWidget);

    QHBoxLayout *row1 = new QHBoxLayout();
    startBtn = new QPushButton("启动游戏");
    startBtn->setFixedSize(120, 35);
    startBtn->setEnabled(false);
    connect(startBtn, &QPushButton::clicked, this, &MainWindow::startGame);
    row1->addWidget(startBtn);

    oddBtn = new QPushButton("启动ODD");
    oddBtn->setFixedSize(120, 35);
    oddBtn->setEnabled(false);
    connect(oddBtn, &QPushButton::clicked, this, &MainWindow::startOdd);
    row1->addWidget(oddBtn);
    buttonLayout->addLayout(row1);

    QHBoxLayout *row2 = new QHBoxLayout();
    updateBtn = new QPushButton("更新");
    updateBtn->setFixedSize(120, 35);
    updateBtn->setEnabled(false);
    connect(updateBtn, &QPushButton::clicked, this, &MainWindow::forceUpdate);
    row2->addWidget(updateBtn);

    hostsBtn = new QPushButton("修改hosts");
    hostsBtn->setFixedSize(120, 35);
    hostsBtn->setEnabled(false);
    connect(hostsBtn, &QPushButton::clicked, this, &MainWindow::modifyHosts);
    row2->addWidget(hostsBtn);
    buttonLayout->addLayout(row2);

    QHBoxLayout *row3 = new QHBoxLayout();
    buyBtn = new QPushButton("购买卡密");
    buyBtn->setFixedSize(120, 35);
    connect(buyBtn, &QPushButton::clicked, this, &MainWindow::openBuyPage);
    row3->addWidget(buyBtn);

    fullUpdateBtn = new QPushButton("更新完整包");
    fullUpdateBtn->setFixedSize(120, 35);
    connect(fullUpdateBtn, &QPushButton::clicked, this, &MainWindow::forceFullUpdate);
    row3->addWidget(fullUpdateBtn);
    buttonLayout->addLayout(row3);

    QHBoxLayout *row4 = new QHBoxLayout();
    wikiBtn = new QPushButton("wiki文档");
    wikiBtn->setFixedSize(120, 35);
    connect(wikiBtn, &QPushButton::clicked, this, &MainWindow::openWikiPage);
    row4->addWidget(wikiBtn);

    // 添加Bug报告按钮
    bugReportBtn = new QPushButton("反馈Bug");
    bugReportBtn->setFixedSize(120, 35);
    connect(bugReportBtn, &QPushButton::clicked, this, &MainWindow::reportBug);
    row4->addWidget(bugReportBtn);

    buttonLayout->addLayout(row4);

        // 在按钮布局中添加设置按钮
    QHBoxLayout *row5 = new QHBoxLayout();
    settingsBtn = new QPushButton();
    settingsBtn->setIcon(QIcon("")); // 设置图标
    settingsBtn->setIconSize(QSize(24, 24)); // 设置图标大小
    settingsBtn->setFixedSize(40, 40); // 设置按钮大小
    settingsBtn->setToolTip("选择更新节点"); // 设置提示
    connect(settingsBtn, &QPushButton::clicked, this, &MainWindow::openSettings);
    row5->addWidget(settingsBtn);
    
    // 添加空白标签使按钮靠左
    QSpacerItem *spacer = new QSpacerItem(40, 20, QSizePolicy::Expanding, QSizePolicy::Minimum);
    row5->addItem(spacer);
    
    buttonLayout->addLayout(row5);

    leftLayout->addWidget(buttonWidget);

    QGroupBox *rightGroup = new QGroupBox("最新公告");
    rightGroup->setStyleSheet("QGroupBox { font-weight: bold; }");
    QVBoxLayout *rightLayout = new QVBoxLayout(rightGroup);

    announcementText = new QTextEdit();
    announcementText->setReadOnly(true);
    announcementText->setText("正在加载公告...");
    announcementText->setStyleSheet("font-size: 10pt;");
    rightLayout->addWidget(announcementText);

    contentLayout->addWidget(leftWidget, 2);
    contentLayout->addWidget(rightGroup, 1);

    mainLayout->addWidget(contentWidget, 1);

    QLabel *footerLabel = new QLabel("闲鱼：小xin喵");
    footerLabel->setStyleSheet("color: gray; font-size: 8pt;");
    mainLayout->addWidget(footerLabel, 0, Qt::AlignRight | Qt::AlignBottom);

    setCentralWidget(centralWidget);
    networkManager = new QNetworkAccessManager(this);
}

// 新增节点设置功能
void MainWindow::openSettings()
{
    QDialog dialog(this);
    dialog.setWindowTitle("选择更新节点");
    dialog.setFixedSize(500, 350); // 增加高度以容纳ping结果
    
    QVBoxLayout *layout = new QVBoxLayout(&dialog);
    
    // 节点选择组
    QGroupBox *nodeGroup = new QGroupBox("选择节点");
    QVBoxLayout *nodeLayout = new QVBoxLayout(nodeGroup);
    
    QButtonGroup *buttonGroup = new QButtonGroup(this);
    
    // 声明按钮变量（确保在函数作用域内）
    QRadioButton *node1Btn = new QRadioButton("节点1 (默认)");
    QRadioButton *node2Btn = new QRadioButton("节点2");
    QRadioButton *node3Btn = new QRadioButton("节点3");
    QRadioButton *testNodeBtn = new QRadioButton("测试节点");

    // 为每个节点创建水平布局（单选按钮 + ping结果）
    QHBoxLayout *node1Layout = new QHBoxLayout();
    node1Layout->addWidget(node1Btn);
    QLabel *pingLabel1 = new QLabel("延迟: 测试中...");
    node1Layout->addWidget(pingLabel1);
    nodeLayout->addLayout(node1Layout);
    
    QHBoxLayout *node2Layout = new QHBoxLayout();
    node2Layout->addWidget(node2Btn);
    QLabel *pingLabel2 = new QLabel("延迟: 测试中...");
    node2Layout->addWidget(pingLabel2);
    nodeLayout->addLayout(node2Layout);
    
    QHBoxLayout *node3Layout = new QHBoxLayout();
    node3Layout->addWidget(node3Btn);
    QLabel *pingLabel3 = new QLabel("延迟: 测试中...");
    node3Layout->addWidget(pingLabel3);
    nodeLayout->addLayout(node3Layout);
    
    QHBoxLayout *testNodeLayout = new QHBoxLayout();
    testNodeLayout->addWidget(testNodeBtn);
    QLabel *pingLabelTest = new QLabel("延迟: 测试中...");
    testNodeLayout->addWidget(pingLabelTest);
    nodeLayout->addLayout(testNodeLayout);

    // 存储ping标签的映射
    pingLabels.clear();
    pingLabels["node1"] = pingLabel1;
    pingLabels["node2"] = pingLabel2;
    pingLabels["node3"] = pingLabel3;
    pingLabels["test"] = pingLabelTest;

    // 设置按钮属性
    node1Btn->setProperty("nodeId", "node1");
    node2Btn->setProperty("nodeId", "node2");
    node3Btn->setProperty("nodeId", "node3");
    testNodeBtn->setProperty("nodeId", "test");
    
    // 添加按钮到组
    buttonGroup->addButton(node1Btn);
    buttonGroup->addButton(node2Btn);
    buttonGroup->addButton(node3Btn);
    buttonGroup->addButton(testNodeBtn);
    
    // 测试节点密码输入
    QHBoxLayout *pwdLayout = new QHBoxLayout();
    QLabel *pwdLabel = new QLabel("测试节点密码:");
    QLineEdit *pwdEdit = new QLineEdit();
    pwdEdit->setEchoMode(QLineEdit::Password);
    pwdLayout->addWidget(pwdLabel);
    pwdLayout->addWidget(pwdEdit);
    nodeLayout->addLayout(pwdLayout);
    
    // 根据当前选择的节点设置单选按钮状态
    foreach(QAbstractButton *btn, buttonGroup->buttons()) {
        if (btn->property("nodeId").toString() == m_currentNode) {
            btn->setChecked(true);
            break;
        }
    }
    
    layout->addWidget(nodeGroup);
    
    // 按钮组
    QHBoxLayout *btnLayout = new QHBoxLayout();
    QPushButton *okBtn = new QPushButton("确定");
    QPushButton *cancelBtn = new QPushButton("取消");
    btnLayout->addWidget(okBtn);
    btnLayout->addWidget(cancelBtn);
    layout->addLayout(btnLayout);
    
    // 连接信号
    connect(okBtn, &QPushButton::clicked, &dialog, &QDialog::accept);
    connect(cancelBtn, &QPushButton::clicked, &dialog, &QDialog::reject);
    
    // 启动ping测试
    startPingTests();
    
    if (dialog.exec() == QDialog::Accepted) {
        QAbstractButton *selectedBtn = buttonGroup->checkedButton();
        if (selectedBtn) {
            QString nodeId = selectedBtn->property("nodeId").toString();
            
            // 如果选择测试节点，验证密码
            if (nodeId == "test") {
                if (pwdEdit->text() != testNodePassword) {
                    QMessageBox::warning(this, "密码错误", "测试节点密码不正确");
                    return;
                }
            }
            
            // 保存节点设置
            saveNodeSettings(nodeId);
            m_currentNode = nodeId;
            updateServerUrl();
            
            QMessageBox::information(this, "设置已保存", "节点设置已更新");
            
            if (isAuthenticated) {
                statusLabel->setText("节点已切换，检查更新...");
                QTimer::singleShot(100, this, &MainWindow::checkForUpdates);
            }
        }
    }
        for (auto it = pingReplies.begin(); it != pingReplies.end(); ++it) {
    if (it.value()) {
        it.value()->abort();
        it.value()->deleteLater();
    }
}
    startPingTests(); // 这会取消所有进行中的请求
    pingLabels.clear();
}

/// 修改startPingTests函数
void MainWindow::startPingTests()
{
    // 清理之前的请求
    for (auto it = pingReplies.begin(); it != pingReplies.end(); ++it) {
        if (it.value()) {
            it.value()->abort();
            it.value()->deleteLater();
        }
    }
    pingReplies.clear();
    
    // 重置标签状态
    for (auto it = pingLabels.begin(); it != pingLabels.end(); ++it) {
        if (it.value()) {
            it.value()->setText("延迟: 测试中...");
            it.value()->setStyleSheet("");
        }
    }
    
    // 为每个节点启动ping测试
    for (auto it = nodeMap.begin(); it != nodeMap.end(); ++it) {
        QString nodeId = it.key();
        QString url = it.value();
        pingNode(url, nodeId);
    }
}

// Ping单个节点
void MainWindow::pingNode(const QString& url, const QString& nodeId)
{
    QNetworkRequest request(url);
    request.setRawHeader("User-Agent", "MaimaiLauncherPing");
    request.setAttribute(QNetworkRequest::Http2AllowedAttribute, false);
    request.setTransferTimeout(5000); // 设置5秒超时

    // 首先解析主机名
    QString host = QUrl(url).host();
    QHostInfo::lookupHost(host, this, [=](const QHostInfo &hostInfo) {
        if (hostInfo.error() != QHostInfo::NoError) {
            updatePingResult(nodeId, -1); // DNS解析失败
            return;
        }

        // 发送实际请求
        QNetworkReply *reply = networkManager->head(request);
        pingReplies[nodeId] = reply;
        
        QElapsedTimer *timer = new QElapsedTimer();
        timer->start();
        
        connect(reply, &QNetworkReply::finished, this, [=]() {
            int latency = -1;
            if (reply->error() == QNetworkReply::NoError) {
                latency = timer->elapsed();
            }
            updatePingResult(nodeId, latency);
            delete timer;
            reply->deleteLater();
            pingReplies.remove(nodeId);
        });
    });
}

// 更新ping结果显示
void MainWindow::updatePingResult(const QString& nodeId, int latency)
{
    if (!pingLabels.contains(nodeId)) {
        return; // 对话框已关闭
    }
    
    // 确保标签仍然有效
    QLabel* label = pingLabels[nodeId];
    if (!label) return;

    if (latency > 0) {
        label->setText(QString("延迟: %1 ms").arg(latency));
        
        // 根据延迟设置颜色
        if (latency < 100) {
            label->setStyleSheet("color: green;");
        } else if (latency < 300) {
            label->setStyleSheet("color: orange;");
        } else {
            label->setStyleSheet("color: red;");
        }
    } else {
        label->setText("延迟: 超时");
        label->setStyleSheet("color: red;");
    }
}

// 保存节点设置
void MainWindow::saveNodeSettings(const QString &nodeId)
{
    settings->setValue("currentNode", nodeId);
    settings->sync();
}

// 加载节点设置
void MainWindow::loadNodeSettings()
{
    m_currentNode = settings->value("currentNode", "node1").toString();
    updateServerUrl();
}

// 更新服务器URL
void MainWindow::updateServerUrl()
{
    if (nodeMap.contains(m_currentNode)) {
        SERVER_URL = nodeMap[m_currentNode];
    } else {
        SERVER_URL = nodeMap["node1"]; // 默认节点
    }
}

void MainWindow::forceFullUpdate()
{
    if (!isAuthenticated) {
        QMessageBox::warning(this, "未验证", "请先完成卡密验证");
        return;
    }

    // 确认用户操作
    if (QMessageBox::question(this, "更新完整包",
                              "确定要下载并安装完整游戏包吗?\n这将覆盖所有本地文件。",
                              QMessageBox::Yes | QMessageBox::No) != QMessageBox::Yes) {
        return;
    }

    // 禁用相关按钮
    fullUpdateBtn->setEnabled(false);
    startBtn->setEnabled(false);
    statusLabel->setText("开始下载完整游戏包...");

    // 调用首次更新函数（该函数已实现完整包下载）
    fetchFirstUpdateVersion();
}

void MainWindow::updateAnnouncement(const QJsonObject &announcement)
{
    QString title = announcement["title"].toString("公告");
    QString date = announcement["date"].toString(QDate::currentDate().toString("yyyy-MM-dd"));
    QString content = announcement["content"].toString("暂无公告内容。");

    announcementText->clear();
    announcementText->append(QString("<div style='color: blue; font-size: 12pt; font-weight: bold;'>%1</div>").arg(title));
    announcementText->append(QString("<div style='color: blue;'>发布日期: %1</div>").arg(date));
    announcementText->append("<hr>");
    announcementText->append(QString("<div style='font-size: 10pt;'>%1</div>").arg(content));
}

void MainWindow::reportBug()
{
    // 创建邮件主题和正文
    QString subject = QString("maimai启动器Bug报告 (v%1)").arg(LAUNCHER_VERSION);
    QString body = QString("设备ID: %1\n\n请描述您遇到的问题：\n").arg(deviceId);

    // 创建mailto链接
    QString mailto = QString("mailto:2932869213@qq.com?subject=%1&body=%2")
                         .arg(QString(QUrl::toPercentEncoding(subject)))
                         .arg(QString(QUrl::toPercentEncoding(body)));

    // 打开默认邮件客户端
    if (!QDesktopServices::openUrl(QUrl(mailto))) {
        QMessageBox::warning(this, "错误", "无法打开邮件客户端。请确保已安装邮件程序。");
    }
}


void MainWindow::activateButtons()
{
    if (isAuthenticated) {
        startBtn->setEnabled(true);
        oddBtn->setEnabled(true);
        updateBtn->setEnabled(true);
        hostsBtn->setEnabled(true);
        fullUpdateBtn->setEnabled(true);
    }
    buyBtn->setEnabled(true);
    pathSelectBtn->setEnabled(true);
    wikiBtn->setEnabled(true);
}

void MainWindow::disableButtons()
{
    startBtn->setEnabled(false);
    oddBtn->setEnabled(false);
    updateBtn->setEnabled(false);
    hostsBtn->setEnabled(false);
    fullUpdateBtn->setEnabled(false);
    wikiBtn->setEnabled(false);
}

void MainWindow::openWikiPage()
{
    QDesktopServices::openUrl(QUrl(""));
}

void MainWindow::checkAdminRights()
{
    BOOL isAdmin = FALSE;
    SID_IDENTIFIER_AUTHORITY NtAuthority = SECURITY_NT_AUTHORITY;
    PSID AdministratorsGroup;

    if (AllocateAndInitializeSid(&NtAuthority, 2, SECURITY_BUILTIN_DOMAIN_RID,
                                 DOMAIN_ALIAS_RID_ADMINS, 0, 0, 0, 0, 0, 0,
                                 &AdministratorsGroup)) {
        if (!CheckTokenMembership(NULL, AdministratorsGroup, &isAdmin)) {
            isAdmin = FALSE;
        }
        FreeSid(AdministratorsGroup);
    }

    if (!isAdmin) {
        QMessageBox::information(this, "权限提升",
                                 "启动器需要管理员权限运行，请允许UAC提示。");

        wchar_t path[MAX_PATH];
        GetModuleFileNameW(NULL, path, MAX_PATH);
        ShellExecuteW(NULL, L"runas", path, NULL, NULL, SW_SHOWNORMAL);
        QApplication::quit();
    }
}


int MainWindow::compareVersions(const QString &v1, const QString &v2)
{
    QStringList parts1 = v1.split('.');
    QStringList parts2 = v2.split('.');
    int maxParts = qMax(parts1.size(), parts2.size());

    for (int i = 0; i < maxParts; i++) {
        int num1 = (i < parts1.size()) ? parts1[i].toInt() : 0;
        int num2 = (i < parts2.size()) ? parts2[i].toInt() : 0;

        if (num1 < num2) return -1;
        if (num1 > num2) return 1;
    }
    return 0;
}

// 修改后的解压函数，支持密码
bool MainWindow::extractZip(const QString &zipPath, const QString &extractDir, const QString &password)
{
    QFile zipFile(zipPath);
    if (!zipFile.exists()) {
        qDebug() << "ZIP文件不存在:" << zipPath;
        return false;
    }

    QDir dir(extractDir);
    if (!dir.exists()) {
        if (!dir.mkpath(".")) {
            qDebug() << "无法创建目录:" << extractDir;
            return false;
        }
    }

    QString program;
    QStringList arguments;
    
    // 尝试多个可能的7z路径
    QString appDir = QCoreApplication::applicationDirPath();
    QStringList possiblePaths = {
        appDir + "/7z/7z.exe",
        appDir + "/7za.exe",
        "C:/Program Files/7-Zip/7z.exe",
        "C:/Program Files (x86)/7-Zip/7z.exe"
    };
    
    bool found7z = false;
    for (const QString &path : possiblePaths) {
        if (QFile::exists(path)) {
            program = path;
            found7z = true;
            break;
        }
    }
    
    if (!found7z) {
        // 尝试在PATH中查找7z
        program = "7z";
        QProcess checkProcess;
        checkProcess.start(program, QStringList() << "--help");
        if (!checkProcess.waitForStarted(3000) || !checkProcess.waitForFinished(3000)) {
            qDebug() << "找不到7z解压程序";
            return false;
        }
    }

    // 设置解压参数
    arguments << "x" << "-y";
    if (!password.isEmpty()) {
        arguments << "-p" + password;
    }
    arguments << "-o" + extractDir;
    arguments << zipPath;
    
    qDebug() << "解压命令:" << program << arguments;

    QProcess process;
    process.setProgram(program);
    process.setArguments(arguments);
    process.start();
    
    // 延长等待时间到10分钟（大型更新可能需要更长时间）
    if (!process.waitForStarted(10000)) { // 10秒内启动
        qDebug() << "无法启动解压进程:" << process.errorString();
        return false;
    }
    
    // 等待解压完成（最长60分钟）
    if (!process.waitForFinished(3600000)) { 
        qDebug() << "解压进程超时:" << process.errorString();
        return false;
    }

    if (process.exitCode() != 0) {
        qDebug() << "解压失败，错误码:" << process.exitCode();
        qDebug() << "错误输出:" << process.readAllStandardError();
        return false;
    }

    qDebug() << "成功解压文件到" << extractDir;
    return true;
}

void MainWindow::startGame()
{
    if (!isAuthenticated) {
        QMessageBox::warning(this, "未验证", "请先完成卡密验证");
        return;
    }

    QString batPath = UPDATE_PATH + "/2-Start.bat";
    if (!QFile::exists(batPath)) {
        QMessageBox::critical(this, "错误", "找不到启动脚本: " + batPath);
        return;
    }

    disableButtons();
    statusLabel->setText("正在启动游戏...");

    // 使用QProcess启动bat文件
    QProcess *gameProcess = new QProcess(this);
    gameProcess->setWorkingDirectory(UPDATE_PATH);

    // 连接游戏结束信号
    connect(gameProcess, QOverload<int, QProcess::ExitStatus>::of(&QProcess::finished),
            this, &MainWindow::onGameFinished);

    // 启动bat文件
    gameProcess->start("cmd.exe", QStringList() << "/c" << batPath);

    if (!gameProcess->waitForStarted()) {
        statusLabel->setText("无法启动游戏");
        activateButtons();
        return;
    }

    statusLabel->setText("游戏运行中...");
}

void MainWindow::startGameProcess()
{
    // 确保 gameProcess 被正确创建
    if (gameProcess) {
        gameProcess->kill();
        gameProcess->deleteLater();
        gameProcess = nullptr;
    }
    gameProcess = new QProcess(this);
    gameProcess->setWorkingDirectory(UPDATE_PATH);

    // 连接游戏结束信号
    connect(gameProcess, QOverload<int, QProcess::ExitStatus>::of(&QProcess::finished),
            this, &MainWindow::onGameFinished);

    // 启动注入程序 - 使用新的 QProcess 实例
    QProcess *injectProcess = new QProcess(this);
    injectProcess->setWorkingDirectory(UPDATE_PATH);

    QStringList injectArgs;
    injectArgs << "-d" << "-k" << "mai2hook.dll" << "amdaemon.exe"
               << "-f" << "-c" << "config_common.json" << "config_server.json" << "config_client.json";

    // 增加超时时间到15秒（15000毫秒）
    injectProcess->start("inject", injectArgs);

    // 增加等待时间到15秒
    if (!injectProcess->waitForFinished(15000)) {
        statusLabel->setText("注入程序超时");
        injectProcess->deleteLater();
        activateButtons();
        return;
    }

    injectProcess->deleteLater();

    // 启动游戏主程序
    QStringList gameArgs;
    gameArgs << "-screen-fullscreen" << "1" << "-screen-width" << "1080" << "-screen-height" << "1920" << "-silent-crashes";

    gameProcess->start("Sinmai.exe", gameArgs);

    if (!gameProcess->waitForStarted()) {
        statusLabel->setText("无法启动游戏");
        activateButtons();
        return;
    }

    statusLabel->setText("游戏运行中...");
}

void MainWindow::onGameFinished(int exitCode, QProcess::ExitStatus exitStatus)
{
    Q_UNUSED(exitCode);
    Q_UNUSED(exitStatus);

    statusLabel->setText("游戏进程已结束");
    activateButtons();

    // 删除QProcess对象
    QProcess *senderProcess = qobject_cast<QProcess*>(sender());
    if (senderProcess) {
        senderProcess->deleteLater();
    }
}

void MainWindow::startOdd()
{
    if (!isAuthenticated) {
        QMessageBox::warning(this, "未验证", "请先完成卡密验证");
        return;
    }

    QString batPath = UPDATE_PATH + "/1-管理员运行odd.bat";
    if (!QFile::exists(batPath)) {
        QMessageBox::critical(this, "错误", "找不到ODD启动脚本: " + batPath);
        return;
    }

    // 启动bat文件
    QProcess::startDetached("cmd.exe", QStringList() << "/c" << batPath, UPDATE_PATH);
    statusLabel->setText("正在启动ODD驱动程序...");
}

void MainWindow::modifyHosts()
{
    if (!isAuthenticated) {
        QMessageBox::warning(this, "未验证", "请先完成卡密验证");
        return;
    }

    QString batPath = UPDATE_PATH + "/hosts.bat";
    if (!QFile::exists(batPath)) {
        QMessageBox::critical(this, "错误", "找不到hosts修改脚本: " + batPath);
        return;
    }

    // 启动bat文件
    QProcess::startDetached("cmd.exe", QStringList() << "/c" << batPath, UPDATE_PATH);
    statusLabel->setText("正在修改hosts文件...");
}

void MainWindow::forceUpdate()
{
    if (!isAuthenticated) {
        QMessageBox::warning(this, "未验证", "请先完成卡密验证");
        return;
    }

    statusLabel->setText("开始强制更新...");
    fetchVersionForForceUpdate();
}

void MainWindow::fetchVersionForForceUpdate()
{
    QUrl url(SERVER_URL + VERSION_FILE);
    QNetworkRequest request(url);
    request.setRawHeader("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36");

    QSslConfiguration sslConfig = QSslConfiguration::defaultConfiguration();
    sslConfig.setPeerVerifyMode(QSslSocket::VerifyNone);
    request.setSslConfiguration(sslConfig);

    QNetworkReply *reply = networkManager->get(request);
    connect(reply, &QNetworkReply::finished, this, [=]() {
        if (reply->error() != QNetworkReply::NoError) {
            statusLabel->setText("连接服务器失败");
            return;
        }

        QByteArray data = reply->readAll();
        QJsonDocument doc = QJsonDocument::fromJson(data);
        if (doc.isNull()) {
            statusLabel->setText("版本信息解析错误");
            return;
        }

        updateGame(doc.object());
        reply->deleteLater();
    });
}

void MainWindow::openBuyPage()
{
    QDesktopServices::openUrl(QUrl("https://m.tb.cn/h.hYesG5B?tk=qva9Vs7587S"));
}

void MainWindow::fetchAnnouncement()
{
    QUrl url(SERVER_URL + "g/" + ANNOUNCEMENT_FILE);
    QNetworkRequest request(url);
    request.setRawHeader("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36");

    QSslConfiguration sslConfig = QSslConfiguration::defaultConfiguration();
    sslConfig.setPeerVerifyMode(QSslSocket::VerifyNone);
    request.setSslConfiguration(sslConfig);

    QNetworkReply *reply = networkManager->get(request);
    connect(reply, &QNetworkReply::finished, this, &MainWindow::onAnnouncementFetched);
}

void MainWindow::onAnnouncementFetched()
{
    QNetworkReply *reply = qobject_cast<QNetworkReply*>(sender());
    QJsonObject announcement;

    if (reply->error() == QNetworkReply::NoError) {
        QByteArray data = reply->readAll();
        QJsonDocument doc = QJsonDocument::fromJson(data);
        if (!doc.isNull()) {
            announcement = doc.object();
        }
    }

    if (announcement.isEmpty()) {
        announcement["title"] = "公告";
        announcement["content"] = "无法连接到服务器获取最新公告。\n请检查网络连接或稍后再试。";
        announcement["date"] = QDate::currentDate().toString("yyyy-MM-dd");
    }

    updateAnnouncement(announcement);
    reply->deleteLater();
}

void MainWindow::checkForUpdates()
{
    if (!isAuthenticated) {
        statusLabel->setText("请先完成卡密验证");
        return;
    }

    // 如果正在进行首次更新，则跳过常规更新检查
    if (m_isFirstUpdateInProgress) {
        qDebug() << "跳过常规更新检查（首次更新进行中）";
        return;
    }

    statusLabel->setText("正在检查更新...");

    QUrl url(SERVER_URL + VERSION_FILE);
    QNetworkRequest request(url);
    request.setRawHeader("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36");

    QSslConfiguration sslConfig = QSslConfiguration::defaultConfiguration();
    sslConfig.setPeerVerifyMode(QSslSocket::VerifyNone);
    request.setSslConfiguration(sslConfig);

    QNetworkReply *reply = networkManager->get(request);
    connect(reply, &QNetworkReply::finished, this, &MainWindow::onVersionChecked);
}

void MainWindow::onVersionChecked()
{
    QNetworkReply *reply = qobject_cast<QNetworkReply*>(sender());
    if (reply->error() != QNetworkReply::NoError) {
        statusLabel->setText("连接服务器失败");
        qDebug() << "连接服务器失败:" << reply->errorString();
        return;
    }

    QByteArray data = reply->readAll();
    QJsonDocument doc = QJsonDocument::fromJson(data);
    if (doc.isNull()) {
        statusLabel->setText("版本信息解析错误");
        qDebug() << "版本信息解析错误";
        return;
    }

    QJsonObject remoteVersion = doc.object();
    QString remoteVer = remoteVersion["version"].toString();
    QString localVer = localVersion["version"].toString();

    qDebug() << "本地版本:" << localVer << "远程版本:" << remoteVer;

    int comparison = compareVersions(remoteVer, localVer);

    if (comparison <= 0) {
        statusLabel->setText("游戏已是最新版本");
        versionLabel->setText("版本: v" + localVer);
        qDebug() << "游戏已是最新版本";
    } else {
        statusLabel->setText("发现新版本 v" + remoteVer);
        versionLabel->setText("版本: v" + localVer + " → v" + remoteVer);
        qDebug() << "需要更新: 本地 v" << localVer << "-> 远程 v" << remoteVer;
        updateGame(remoteVersion); // 执行增量更新
    }

    reply->deleteLater();
}

void MainWindow::updateGame(const QJsonObject &remoteVersion)
{
    if (remoteVersion.isEmpty()) {
        statusLabel->setText("无效的版本信息");
        return;
    }

    QString remoteVer = remoteVersion["version"].toString();
    QString localVer = localVersion["version"].toString();

    // 检查下载URL是否存在
    if (!remoteVersion.contains("url") || remoteVersion["url"].toString().isEmpty()) {
        statusLabel->setText("更新URL无效");
        return;
    }

    QString updateUrl = remoteVersion["url"].toString();

    disableButtons();
    statusLabel->setText("正在下载增量更新...");

    QUrl url(updateUrl); // 使用从JSON中获取的URL
    QNetworkRequest request(url);
    request.setRawHeader("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36");

    QSslConfiguration sslConfig = QSslConfiguration::defaultConfiguration();
    sslConfig.setPeerVerifyMode(QSslSocket::VerifyNone);
    request.setSslConfiguration(sslConfig);

    QNetworkReply *reply = networkManager->get(request);
    connect(reply, &QNetworkReply::downloadProgress, this, [=](qint64 bytesReceived, qint64 bytesTotal) {
        if (bytesTotal > 0) {
            int percent = static_cast<int>((bytesReceived * 100) / bytesTotal);
            progressBar->setValue(percent);
            statusLabel->setText(QString("下载增量更新: %1%").arg(percent));
        }
    });

    connect(reply, &QNetworkReply::finished, this, [=]() {
        onUpdateDownloaded(reply, remoteVersion);
    });
}

void MainWindow::onUpdateDownloaded(QNetworkReply *reply, const QJsonObject &version)
{
    if (reply->error() != QNetworkReply::NoError) {
        statusLabel->setText("下载失败: " + reply->errorString());
        qDebug() << "下载失败:" << reply->errorString();
        activateButtons();
        return;
    }

    QByteArray data = reply->readAll();
    QFile file(UPDATE_ZIP);
    if (file.open(QIODevice::WriteOnly)) {
        file.write(data);
        file.close();
    } else {
        qDebug() << "无法保存更新文件";
    }

    statusLabel->setText("正在解压文件...");
    progressBar->setValue(0);

    // 从版本信息中获取密码
    QString password = version["password"].toString();

    QFutureWatcher<bool> *watcher = new QFutureWatcher<bool>(this);
    connect(watcher, &QFutureWatcher<bool>::finished, this, [=]() {
        if (watcher->result()) {
            // 更新版本信息并保存
            QJsonObject newLocalVersion;
            newLocalVersion["version"] = version["version"].toString();

            if (version.contains("changelog")) {
                newLocalVersion["changelog"] = version["changelog"];
            }
            if (version.contains("timestamp")) {
                newLocalVersion["timestamp"] = version["timestamp"];
            }

            localVersion = newLocalVersion;
            saveLocalVersion();

            // 重新加载本地版本以确保一致性
            loadLocalVersion();

            // 更新界面显示
            versionLabel->setText("版本: v" + localVersion["version"].toString());
            statusLabel->setText("更新完成!");
            progressBar->setValue(100);

            QFile::remove(UPDATE_ZIP);
            QMessageBox::information(this, "更新完成", "游戏已成功更新到最新版本!");
            qDebug() << "更新完成: v" << localVersion["version"].toString();
        } else {
            statusLabel->setText("解压失败");
            QMessageBox::critical(this, "更新失败", "解压更新包失败");
            qDebug() << "解压失败";
        }
        activateButtons();
        watcher->deleteLater();
    });

    QFuture<bool> future = QtConcurrent::run([=]() {
        return extractZip(UPDATE_ZIP, UPDATE_PATH, password);
    });
    watcher->setFuture(future);

    reply->deleteLater();
}

void MainWindow::saveLocalVersion()
{
    // 创建精简的版本对象
    QJsonObject saveVersion;
    saveVersion["version"] = localVersion["version"].toString();

    // 只保存必要的字段
    if (localVersion.contains("changelog")) {
        saveVersion["changelog"] = localVersion["changelog"];
    }
    if (localVersion.contains("timestamp")) {
        saveVersion["timestamp"] = localVersion["timestamp"];
    }

    QFile file(UPDATE_PATH + "/" + VERSION_FILE);
    if (file.open(QIODevice::WriteOnly)) {
        QJsonDocument doc(saveVersion);
        file.write(doc.toJson());
        file.close();
    }
}

void MainWindow::selectPackagePath()
{
    QString dir = QFileDialog::getExistingDirectory(
        this,
        tr("选择Package目录"),
        UPDATE_PATH,
        QFileDialog::ShowDirsOnly | QFileDialog::DontResolveSymlinks
        );

    if (!dir.isEmpty()) {
        UPDATE_PATH = dir;
        pathLabel->setText(UPDATE_PATH);

        // 更新相关文件路径
        BAT_FILE = UPDATE_PATH + "/2-Start.bat";
        ODD_BAT_FILE = UPDATE_PATH + "/1-管理员运行odd.bat";
        HOSTS_BAT = UPDATE_PATH + "/hosts.bat";

        // 重新加载本地版本
        loadLocalVersion();
        checkPackageExists();
        saveSettings();
    }
}

void MainWindow::checkPackageExists()
{
    QDir packageDir(UPDATE_PATH);
    bool exists = packageDir.exists();

    startBtn->setEnabled(false);
    oddBtn->setEnabled(false);
    hostsBtn->setEnabled(false);
    wikiBtn->setEnabled(true);
    fullUpdateBtn->setEnabled(isAuthenticated);

    updateBtn->setEnabled(isAuthenticated);
    buyBtn->setEnabled(true);
    pathSelectBtn->setEnabled(true);


    if (!exists) {
        statusLabel->setText("警告: Package目录不存在!");
    } else if (isAuthenticated) {
        startBtn->setEnabled(true);
        oddBtn->setEnabled(true);
        hostsBtn->setEnabled(true);
    }
}

void MainWindow::saveSettings()
{
    settings->setValue("packagePath", UPDATE_PATH);
    settings->sync();
}

void MainWindow::loadSettings()
{
    if (settings->contains("packagePath")) {
        UPDATE_PATH = settings->value("packagePath").toString();
    } else {
        UPDATE_PATH = "Package";
    }

    BAT_FILE = UPDATE_PATH + "/2-Start.bat";
    ODD_BAT_FILE = UPDATE_PATH + "/1-管理员运行odd.bat";
    HOSTS_BAT = UPDATE_PATH + "/hosts.bat";
}

// 修改 getDeviceId 函数
QString MainWindow::getDeviceId()
{
    ensureDataDirExists();

    // 确定数据目录路径
    QString dataDir = "D:/maimaiLauncherData";
    QDir dDrive("D:/");
    if (!dDrive.exists()) {
        dataDir = "C:/maimaiLauncherData";
    }
    DEVICE_CODE_FILE = dataDir + "/device_code.dat";

    QFile file(DEVICE_CODE_FILE);
    if (file.exists() && file.open(QIODevice::ReadOnly)) {
        QString id = QString::fromUtf8(file.readAll()).trimmed();
        file.close();
        if (!id.isEmpty()) return id;
    }

    QString deviceInfo = "";

    HKEY hKey;
    if (RegOpenKeyEx(HKEY_LOCAL_MACHINE, L"HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0",
                     0, KEY_READ, &hKey) == ERROR_SUCCESS) {
        wchar_t cpuName[256];
        DWORD size = sizeof(cpuName);
        DWORD type;

        if (RegQueryValueEx(hKey, L"ProcessorNameString", NULL, &type,
                            (LPBYTE)cpuName, &size) == ERROR_SUCCESS) {
            deviceInfo += QString::fromWCharArray(cpuName);
        }
        RegCloseKey(hKey);
    }

    if (RegOpenKeyEx(HKEY_LOCAL_MACHINE, L"HARDWARE\\DEVICEMAP\\Scsi\\Scsi Port 0\\Scsi Bus 0\\Target Id 0\\Logical Unit Id 0",
                     0, KEY_READ, &hKey) == ERROR_SUCCESS) {
        wchar_t diskId[256];
        DWORD size = sizeof(diskId);
        DWORD type;

        if (RegQueryValueEx(hKey, L"SerialNumber", NULL, &type,
                            (LPBYTE)diskId, &size) == ERROR_SUCCESS) {
            deviceInfo += QString::fromWCharArray(diskId);
        }
        RegCloseKey(hKey);
    }

    QCryptographicHash hash(QCryptographicHash::Sha256);
    hash.addData(deviceInfo.toUtf8());
    QString deviceId = hash.result().toHex().left(32);

    if (file.open(QIODevice::WriteOnly)) {
        file.write(deviceId.toUtf8());
        file.close();

        const wchar_t* path = reinterpret_cast<const wchar_t*>(DEVICE_CODE_FILE.utf16());
        DWORD attributes = GetFileAttributesW(path);
        if (attributes != INVALID_FILE_ATTRIBUTES) {
            SetFileAttributesW(path, attributes | FILE_ATTRIBUTE_HIDDEN);
        }
    }

    return deviceId;
}

QString MainWindow::loadSavedKami()
{
    ensureDataDirExists();

    // 确定数据目录路径
    QString dataDir = "D:/maimaiLauncherData";
    QDir dDrive("D:/");
    if (!dDrive.exists()) {
        dataDir = "C:/maimaiLauncherData";
    }
    CARD_FILE = dataDir + "/card.dat";

    QFile file(CARD_FILE);
    if (file.exists() && file.open(QIODevice::ReadOnly)) {
        QString kami = QString::fromUtf8(file.readAll()).trimmed();
        file.close();
        return kami;
    }
    return "";
}

bool MainWindow::saveKami(const QString &kami)
{
    ensureDataDirExists();

    // 确定数据目录路径
    QString dataDir = "D:/maimaiLauncherData";
    QDir dDrive("D:/");
    if (!dDrive.exists()) {
        dataDir = "C:/maimaiLauncherData";
    }
    CARD_FILE = dataDir + "/card.dat";

    QFile file(CARD_FILE);
    if (file.open(QIODevice::WriteOnly)) {
        file.write(kami.toUtf8());
        file.close();

        const wchar_t* path = reinterpret_cast<const wchar_t*>(CARD_FILE.utf16());
        DWORD attributes = GetFileAttributesW(path);
        if (attributes != INVALID_FILE_ATTRIBUTES) {
            SetFileAttributesW(path, attributes | FILE_ATTRIBUTE_HIDDEN);
        }
        return true;
    }
    return false;
}

bool MainWindow::clearSavedKami()
{
    // 确定数据目录路径
    QString dataDir = "D:/maimaiLauncherData";
    QDir dDrive("D:/");
    if (!dDrive.exists()) {
        dataDir = "C:/maimaiLauncherData";
    }
    CARD_FILE = dataDir + "/card.dat";

    QFile file(CARD_FILE);
    return file.exists() ? file.remove() : true;
}

void MainWindow::showAuthWindow()
{
    if (authWindow) {
        authWindow->deleteLater();
    }

    authWindow = new AuthWindow(deviceId, savedKami, this);
    if (authWindow->exec() == QDialog::Accepted) {
        QString kami = authWindow->getKami();
        bool remember = authWindow->getRemember();

        if (!kami.isEmpty()) {
            authStatus->setText("验证中...");
            performNetworkAuthentication(kami, remember);
        }
    } else {
        authStatus->setText("验证已取消");
        QMessageBox::critical(this, "验证取消", "您必须完成验证才能使用启动器。\n程序将在5秒后关闭...");
        quitTimer->start(5000);
    }
}

void MainWindow::performNetworkAuthentication(const QString &kami, bool remember)
{
    QUrl url(AUTH_API);
    QUrlQuery query;
    query.addQueryItem("api", "kmlogon");
    query.addQueryItem("app", APP_ID);
    query.addQueryItem("kami", kami);
    query.addQueryItem("markcode", deviceId);
    url.setQuery(query);

    QNetworkRequest request(url);
    request.setRawHeader("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36");

    QSslConfiguration sslConfig = QSslConfiguration::defaultConfiguration();
    sslConfig.setPeerVerifyMode(QSslSocket::VerifyNone);
    request.setSslConfiguration(sslConfig);

    QNetworkReply *reply = networkManager->get(request);

    connect(reply, &QNetworkReply::finished, this, [=]() {
        QString errorMsg;
        QString vipExpiry;
        bool success = false;

        if (reply->error() == QNetworkReply::NoError) {
            QByteArray data = reply->readAll();
            QJsonDocument doc = QJsonDocument::fromJson(data);

            if (!doc.isNull() && doc.isObject()) {
                QJsonObject json = doc.object();
                int code = json["code"].toInt(-1);

                if (json.contains("code")) {
                    if (code == 200) {
                        if (json.contains("msg") && json["msg"].isObject()) {
                            QJsonObject msg = json["msg"].toObject();
                            if (msg.contains("vip")) {
                                vipExpiry = msg["vip"].toString();
                                success = true;
                                errorMsg = "验证成功";
                            } else {
                                errorMsg = "服务器响应缺少vip字段";
                            }
                        } else {
                            errorMsg = "服务器响应格式错误";
                        }
                    } else {
                        QMap<int, QString> errorMap = {
                            {101, "应用不存在 (101)"},
                            {102, "应用已关闭 (102)"},
                            {171, "接口维护中 (171)"},
                            {172, "接口未添加或不存在 (172)"},
                            {104, "签名为空 (104)"},
                            {105, "数据过期 (105)"},
                            {106, "签名有误 (106)"},
                            {148, "卡密为空 (148)"},
                            {149, "卡密不存在 (149)"},
                            {150, "已使用 (150)"},
                            {151, "卡密禁用 (151)"},
                            {169, "IP不一致 (169)"}
                        };

                        errorMsg = errorMap.value(code, "未知错误 (代码: " + QString::number(code) + ")");
                    }
                } else {
                    errorMsg = "服务器响应缺少code字段";
                }
            } else {
                errorMsg = "响应解析错误: " + data;
            }
        } else {
            errorMsg = "网络错误: " + reply->errorString() + " (代码: " + QString::number(reply->error()) + ")";
        }

        reply->deleteLater();
        onAuthenticationFinished(kami, remember, success, errorMsg, vipExpiry);
    });
}

void MainWindow::onAuthenticationFinished(const QString &kami, bool remember, bool success, const QString &message, const QString &vipExpiry)
{
    authStatus->setText(message);

    if (success) {
        isAuthenticated = true;
        QDateTime expireTime = QDateTime::fromSecsSinceEpoch(vipExpiry.toLongLong());
        QString expireStr = expireTime.toString("yyyy-MM-dd HH:mm:ss");
        vipInfo->setText("VIP到期: " + expireStr);

        if (remember) {
            if (saveKami(kami)) {
                savedKami = kami;
            } else {
                authStatus->setText(authStatus->text() + " (保存卡密失败)");
            }
        } else {
            clearSavedKami();
            savedKami = "";
        }

        // 如果是首次启动
        if (isFirstLaunch) {
            // 提示选择Package目录
            QMessageBox::information(this, "首次启动", "请选择游戏Package目录");
            selectPackagePath();

            // 提示首次更新 - 使用update_f.json
            if (QMessageBox::question(this, "首次启动", "检测到第一次启动，是否立即进行首次更新？",
                                      QMessageBox::Yes | QMessageBox::No) == QMessageBox::Yes) {
                statusLabel->setText("开始首次更新...");
                fetchFirstUpdateVersion(); // 调用首次更新函数
            } else {
                // 用户选择不进行首次更新，直接检查常规更新
                checkForUpdates(); // 新增：非首次启动时检查更新
            }

            isFirstLaunch = false;  // 标记已处理首次启动
        } else {
            // 非首次启动，直接检查常规更新
            checkForUpdates(); // 新增：非首次启动时检查更新
        }

        activateButtons();
        fullUpdateBtn->setEnabled(true);
        checkPackageExists();
        checkLauncherVersion(); // 检查启动器版本
        checkAndDeleteFiles();
    } else {
        isAuthenticated = false;
        vipInfo->setText("VIP状态: 验证失败");
        clearSavedKami();
        savedKami = "";
        disableButtons();
        QMessageBox::critical(this, "验证失败", "验证失败: " + message + "\n程序将在5秒后关闭...");
        quitTimer->start(5000);
    }
}

void MainWindow::checkAndDeleteFiles()
{
    QUrl url(SERVER_URL + "delete.json");
    QNetworkRequest request(url);
    request.setRawHeader("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36");

    QSslConfiguration sslConfig = QSslConfiguration::defaultConfiguration();
    sslConfig.setPeerVerifyMode(QSslSocket::VerifyNone);
    request.setSslConfiguration(sslConfig);

    QNetworkReply *reply = networkManager->get(request);
    connect(reply, &QNetworkReply::finished, this, [=]() {
        if (reply->error() != QNetworkReply::NoError) {
            qDebug() << "无法获取删除列表:" << reply->errorString();
            return;
        }

        QByteArray data = reply->readAll();
        QJsonDocument doc = QJsonDocument::fromJson(data);
        if (doc.isNull() || !doc.isArray()) {
            qDebug() << "删除列表格式错误";
            return;
        }

        QJsonArray filesToDelete = doc.array();
        processDeleteList(filesToDelete);
        reply->deleteLater();
    });
}

void MainWindow::processDeleteList(const QJsonArray &filesToDelete)
{
    int deletedCount = 0;
    int failedCount = 0;

    for (const QJsonValue &value : filesToDelete) {
        QString relativePath = value.toString();
        if (relativePath.isEmpty()) continue;

        QString fullPath = UPDATE_PATH + "/" + relativePath;
        QFile file(fullPath);

        if (file.exists()) {
            // 如果是只读文件，先取消只读属性
            const wchar_t* wPath = reinterpret_cast<const wchar_t*>(fullPath.utf16());
            DWORD attrs = GetFileAttributesW(wPath);
            if (attrs != INVALID_FILE_ATTRIBUTES && (attrs & FILE_ATTRIBUTE_READONLY)) {
                SetFileAttributesW(wPath, attrs & ~FILE_ATTRIBUTE_READONLY);
            }
            if (file.remove()) {
                qDebug() << "已删除文件:" << fullPath;
                deletedCount++;
            } else {
                qDebug() << "删除失败:" << fullPath << file.errorString();
                failedCount++;
            }
        }
    }

    if (deletedCount > 0 || failedCount > 0) {
        qDebug() << "删除操作完成: 成功删除" << deletedCount
                 << "个文件," << failedCount << "个文件删除失败";
    }
}

void MainWindow::fetchFirstUpdateVersion()
{
    m_isFirstUpdateInProgress = true; // 标记首次更新开始

    QUrl url(SERVER_URL + UPDATE_F_VERSION_FILE);
    QNetworkRequest request(url);
    request.setRawHeader("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36");

    QSslConfiguration sslConfig = QSslConfiguration::defaultConfiguration();
    sslConfig.setPeerVerifyMode(QSslSocket::VerifyNone);
    request.setSslConfiguration(sslConfig);

    QNetworkReply *reply = networkManager->get(request);
    connect(reply, &QNetworkReply::finished, this, [=]() {
        if (reply->error() != QNetworkReply::NoError) {
            statusLabel->setText("首次更新: 连接服务器失败");
            m_isFirstUpdateInProgress = false;
            return;
        }

        QByteArray data = reply->readAll();
        QJsonDocument doc = QJsonDocument::fromJson(data);
        if (doc.isNull()) {
            statusLabel->setText("首次更新: 版本信息解析错误");
            m_isFirstUpdateInProgress = false;
            return;
        }

        QJsonObject remoteVersion = doc.object();
        QString remoteVer = remoteVersion["version"].toString();
        statusLabel->setText("首次更新: 下载完整包 " + remoteVer);

        // 使用新的文件名
        QString FULL_UPDATE_ZIP = "update_f.zip";

        // 获取完整包URL
        QString updateUrl = remoteVersion["url"].toString();
        if (updateUrl.isEmpty()) {
            statusLabel->setText("首次更新: URL无效");
            m_isFirstUpdateInProgress = false;
            return;
        }

        // 从版本信息中获取密码
        QString password = remoteVersion["password"].toString();

        // 下载完整包
        QUrl fullUrl(updateUrl);
        QNetworkRequest fullRequest(fullUrl);
        fullRequest.setRawHeader("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36");
        fullRequest.setSslConfiguration(sslConfig);

        QNetworkReply *downloadReply = networkManager->get(fullRequest);
        connect(downloadReply, &QNetworkReply::downloadProgress, this, [=](qint64 bytesReceived, qint64 bytesTotal) {
            if (bytesTotal > 0) {
                int percent = static_cast<int>((bytesReceived * 100) / bytesTotal);
                progressBar->setValue(percent);
                statusLabel->setText(QString("下载完整包: %1%").arg(percent));
            }
        });

        connect(downloadReply, &QNetworkReply::finished, this, [=]() {
            if (downloadReply->error() != QNetworkReply::NoError) {
                statusLabel->setText("完整包下载失败: " + downloadReply->errorString());
                m_isFirstUpdateInProgress = false;
                return;
            }

            // 保存完整包
            QByteArray fullData = downloadReply->readAll();
            QFile fullFile(FULL_UPDATE_ZIP);
            if (fullFile.open(QIODevice::WriteOnly)) {
                fullFile.write(fullData);
                fullFile.close();
            }

            statusLabel->setText("正在解压完整包...");
            progressBar->setValue(0);

            QFutureWatcher<bool> *watcher = new QFutureWatcher<bool>(this);
            connect(watcher, &QFutureWatcher<bool>::finished, this, [=]() {
                if (watcher->result()) {
                    // 更新版本信息并保存
                    QJsonObject newLocalVersion;
                    newLocalVersion["version"] = remoteVersion["version"].toString();

                    if (remoteVersion.contains("changelog")) {
                        newLocalVersion["changelog"] = remoteVersion["changelog"];
                    }
                    if (remoteVersion.contains("timestamp")) {
                        newLocalVersion["timestamp"] = remoteVersion["timestamp"];
                    }

                    localVersion = newLocalVersion;
                    saveLocalVersion();

                    // 更新界面显示
                    versionLabel->setText("版本: v" + remoteVer);
                    statusLabel->setText("首次更新完成!");
                    progressBar->setValue(100);

                    QFile::remove(FULL_UPDATE_ZIP);
                    QMessageBox::information(this, "首次更新完成", "游戏已成功安装完整包!");

                    // 标记首次更新完成
                    m_isFirstUpdateInProgress = false;

                    // 立即执行一次增量更新检查
                    statusLabel->setText("检查增量更新...");
                    checkForUpdates();
                } else {
                    statusLabel->setText("解压完整包失败");
                    m_isFirstUpdateInProgress = false;
                }
                watcher->deleteLater();
            });

            QFuture<bool> future = QtConcurrent::run([=]() {
                return extractZip(FULL_UPDATE_ZIP, UPDATE_PATH, password);
            });
            watcher->setFuture(future);

            downloadReply->deleteLater();
        });

        reply->deleteLater();
    });
}

// 检查启动器版本
void MainWindow::checkLauncherVersion()
{
    QUrl url(SERVER_URL + "launcher_version.json");
    QNetworkRequest request(url);
    request.setRawHeader("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36");

    QSslConfiguration sslConfig = QSslConfiguration::defaultConfiguration();
    sslConfig.setPeerVerifyMode(QSslSocket::VerifyNone);
    request.setSslConfiguration(sslConfig);

    QNetworkReply *reply = networkManager->get(request);
    connect(reply, &QNetworkReply::finished, this, [=]() {
        if (reply->error() != QNetworkReply::NoError) {
            // 无法连接服务器，弹窗提示并闪退
            QMessageBox::critical(nullptr, "网络错误", "无法连接服务器，启动器即将关闭");
            QTimer::singleShot(0, this, &MainWindow::quitApplication);
            return;
        }

        QByteArray data = reply->readAll();
        QJsonDocument doc = QJsonDocument::fromJson(data);
        if (doc.isNull() || !doc.isObject()) {
            // 数据解析错误，不退出
            qDebug() << "启动器版本信息解析错误";
            return;
        }

        QJsonObject remoteData = doc.object();
        QString remoteVersion = remoteData["version"].toString();
        QString downloadUrl = remoteData["url"].toString(); // 保留但不再使用

        if (compareVersions(remoteVersion, LAUNCHER_VERSION) > 0) {
            // 当前版本过旧
            QMessageBox msgBox;
            msgBox.setWindowTitle("启动器版本过旧");
            msgBox.setText(QString("发现新版本启动器 v%1，当前版本 v%2。请下载最新版本启动器。\n程序将在5秒后关闭。").arg(remoteVersion).arg(LAUNCHER_VERSION));
            msgBox.setStandardButtons(QMessageBox::Ok);
            msgBox.exec();

            // 5秒后退出
            QTimer::singleShot(5000, this, &MainWindow::quitApplication);
        }

        reply->deleteLater();
    });
}

void MainWindow::quitApplication()
{
    QApplication::quit();
}
