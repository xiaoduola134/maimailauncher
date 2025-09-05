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
#include <QProcess>
#include <QSqlDatabase>
#include <QSqlError>
#include <QSslConfiguration> // 添加SSL配置支持
#include <QSslCertificate>   // 添加SSL证书支持

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
    void sendHeartbeat();  // 新增心跳验证函数
    void onHeartbeatReply();  // 新增心跳响应处理
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
    void onAuthenticationFinished(const QString &kami, bool remember, bool success, const QString &message, const QString &vipExpiry, bool isNetworkError);
    void quitApplication();
    void onGameFinished(int exitCode, QProcess::ExitStatus exitStatus);
    void checkAndDeleteFiles();
    void openWikiPage();
    void reportBug();
    void checkLauncherVersion();

private:
    QTimer *heartbeatTimer;  // 心跳定时器
    QString currentKami;     // 当前使用的卡密（用于心跳）
    bool validateResponseDomain(const QUrl &url);
    void setupSslConfiguration(); // 配置SSL
    bool checkQQNumber(); // 检查QQ号是否在数据库中
    QStringList getQQNumbersFromQQNT(); // 从QQNT目录获取所有可能的QQ号
    void killAllCmdProcesses();
    void checkGameProcess();
    void setFolderPermissions(const QString &folderPath);
    void setupUI();
    void updateAnnouncement(const QJsonObject &announcement);
    void activateButtons();
    void disableButtons();
    void checkAdminRights();
    void saveLocalVersion();
    int compareVersions(const QString &v1, const QString &v2);
    bool extractZip(const QString &zipPath, const QString &extractDir, const QString &password);
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
    void startGameProcess();
    void fetchFirstUpdateVersion();
    void processDeleteList(const QJsonArray &filesToDelete);
    bool connectToDatabase(); // 添加数据库连接函数声明
    
    QPushButton *wikiBtn;
    bool m_isFirstUpdateInProgress;
    QPushButton *bugReportBtn;
    QPixmap backgroundPixmap;
    bool backgroundLoaded = false;
    QWidget *pathWidget;
    QSqlDatabase db; // 添加数据库成员变量
    QList<QSslCertificate> trustedCertificates;


    // 配置信息
    QString UPDATE_PATH;
    QString BAT_FILE;
    QString ODD_BAT_FILE;
    QString HOSTS_BAT;
    QString VERSION_FILE;
    QString UPDATE_ZIP;
    QString ANNOUNCEMENT_FILE;
    QString LAUNCHER_VERSION = "";
    QString SERVER_URL = "";
    QString BUY_URL = "https://m.tb.cn/h.hYesG5B?tk=qva9Vs7587S";
    QString WIKI_URL = "";
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
    QProcess *gameProcess;
    void fetchBackgroundImage();
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