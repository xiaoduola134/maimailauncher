#ifndef MAINWINDOW_H
#define MAINWINDOW_H

#include <QMainWindow>
#include <QNetworkAccessManager>
#include <QJsonObject>
#include <QLabel>
#include <QPushButton>
#include <QProgressBar>
#include <QTextEdit>
#include <QGroupBox>
#include <QFileDialog>
#include <QSettings>
#include <QDir>
#include <QLineEdit>
#include <QDialog>
#include <QCheckBox>
#include <QTimer>
#include <QMessageBox>
#include <QApplication>
#include <QProcess> // 添加QProcess头文件

QT_BEGIN_NAMESPACE
namespace Ui { class MainWindow; }
QT_END_NAMESPACE

class AuthWindow;

class MainWindow : public QMainWindow
{
    Q_OBJECT

public:
    MainWindow(QWidget *parent = nullptr);
    ~MainWindow();

private slots:
    void startGame();
    void startOdd();
    void modifyHosts();
    void forceUpdate();
    void openBuyPage();
    void fetchAnnouncement();
    void onAnnouncementFetched();
    void checkForUpdates();
    void onVersionChecked();
    void updateGame(const QJsonObject &remoteVersion = QJsonObject());
    void onUpdateDownloaded(QNetworkReply *reply, const QJsonObject &version);
    void selectPackagePath();
    void showAuthWindow();
    void forceFullUpdate();
    void onAuthenticationFinished(const QString &kami, bool remember, bool success, const QString &message, const QString &vipExpiry);
    void quitApplication();
    void onGameFinished(int exitCode, QProcess::ExitStatus exitStatus); // 添加游戏进程结束信号槽
    void checkAndDeleteFiles();
    void openWikiPage();
    void reportBug(); // 添加报告Bug的槽函数
    void checkLauncherVersion(); // 检查启动器版本
    void openSettings(); // 新增设置功能

private:
    void setupUI();
    void updateAnnouncement(const QJsonObject &announcement);
    void activateButtons();
    void disableButtons();
    void checkAdminRights();
    void saveLocalVersion();
    int compareVersions(const QString &v1, const QString &v2);
    bool extractZip(const QString &zipPath, const QString &extractDir, const QString &password); // 增加密码参数
    void saveSettings();
    void loadSettings();
    void checkPackageExists();
    QString getDeviceId();
    QString loadSavedKami();
    bool saveKami(const QString &kami);
    bool clearSavedKami();
    void performNetworkAuthentication(const QString &kami, bool remember);
    void loadLocalVersion();
    void fetchVersionForForceUpdate();
    void startGameProcess(); // 添加游戏启动函数
    void fetchFirstUpdateVersion();
    void processDeleteList(const QJsonArray &filesToDelete);
    QPushButton *wikiBtn;
    bool m_isFirstUpdateInProgress;
    QPushButton *bugReportBtn; // 添加Bug报告按钮
    QPixmap backgroundPixmap;
    bool backgroundLoaded = false;
    QWidget *pathWidget;
    QWidget *contentWidget;
    QWidget *leftWidget;
    QWidget *buttonWidget;
    QGroupBox *rightGroup;
    QPushButton *settingsBtn; // 新增设置按钮
    void saveNodeSettings(const QString &nodeId); // 新增节点设置保存
    void loadNodeSettings(); // 新增节点设置加载
    void updateServerUrl(); // 更新服务器URL
    void startPingTests();
    void pingNode(const QString& url, const QString& nodeId);
    void updatePingResult(const QString& nodeId, int latency);
    QMap<QString, QNetworkReply*> pingReplies; // 存储每个节点的网络请求
    void checkExtractorAvailability();

    // 配置信息
    QString SERVER_URL;
    QString UPDATE_PATH;
    QString BAT_FILE;
    QString ODD_BAT_FILE;
    QString HOSTS_BAT;
    QString VERSION_FILE;
    QString UPDATE_ZIP;
    QString ANNOUNCEMENT_FILE;
    QString LAUNCHER_VERSION = "2.3.0"; // 更新版本号
    QString AUTH_API = "";
    QString APP_ID = "";
    QString DEVICE_CODE_FILE;
    QString CARD_FILE;

    // UI元素
    QLabel *statusLabel;
    QLabel *versionLabel;
    QLabel *authStatus;
    QLabel *vipInfo;
    QProgressBar *progressBar;
    QTextEdit *announcementText;
    QPushButton *startBtn;
    QPushButton *oddBtn;
    QPushButton *updateBtn;
    QPushButton *hostsBtn;
    QPushButton *buyBtn;
    QPushButton *fullUpdateBtn;
    QPushButton *pathSelectBtn;
    QLabel *pathLabel;

    // 其他成员
    QNetworkAccessManager *networkManager;
    QJsonObject localVersion;
    QSettings *settings;
    QString deviceId;
    QString savedKami;
    bool isAuthenticated = false;
    AuthWindow *authWindow = nullptr;
    QTimer *quitTimer = nullptr;
    bool isFirstLaunch = false;
    QProcess *gameProcess; // 添加游戏进程
    void fetchBackgroundImage();
    QString m_currentNode; // 当前选择的节点ID
    QMap<QString, QString> nodeMap; // 节点ID到URL的映射
    QString testNodePassword; // 测试节点密码
    QMap<QString, QLabel*> pingLabels; // 存储节点ID到标签的映射
    QMap<QString, QString> nodeHostMap; // 存储节点ID到主机名的映射
};

class AuthWindow : public QDialog
{
    Q_OBJECT

public:
    explicit AuthWindow(const QString &deviceId, const QString &savedKami, QWidget *parent = nullptr);
    QString getKami() const;
    bool getRemember() const;

private:
    QLineEdit *kamiEntry;
    QCheckBox *rememberCheck;
};
#endif // MAINWINDOW_H
