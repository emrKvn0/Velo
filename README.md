# 🎵 Spotify Skipper

[Türkçe](#türkçe) | [English](#english)

---

<br>

<h2 id="türkçe">🇹🇷 Türkçe</h2>

**Spotify Skipper**, fare hareketlerinizi (kavisli kaydırma - swipe) kullanarak Spotify, YouTube ve diğer medya oynatıcılarında arka planda şarkı değiştirmenize olanak tanıyan, sistem tepsisinde (system tray) çalışan hafif ve modern bir Windows arka plan uygulamasıdır.

### ✨ Özellikler

* **Hareketle Kontrol (Gesture Control):** Farenizi ekranın sağ veya sol üst/orta kenarlarına kavisli bir şekilde (aşağı doğru ivmelenerek) çarptırarak şarkıları ileri veya geri sarabilirsiniz.
* **Güvenlik Kilidi (Security Lock):** İstem dışı şarkı atlamalarını önlemek için eylemlerin sadece **Sol CTRL** tuşuna basılı tutulduğunda gerçekleşmesini sağlayan koruma modu.
* **Sistem Tepsisi Entegrasyonu (System Tray):** Tamamen arka planda çalışır. Pencereyi kapattığınızda sağ alt köşeye (tray) gizlenir.
* **Otomatik Başlatma (Run on Startup):** Windows başladığında arka planda sessizce (konsol ekranı olmadan) çalışmaya başlama seçeneği.
* **Modern Arayüz:** PySide6 kullanılarak tasarlanmış sade, anlaşılır ve kullanımı kolay, minimalist bir kontrol paneli.

### 🛠️ Kurulum & Gereksinimler

* **İşletim Sistemi:** Windows
* **Python Sürümü:** Python 3.x

1. Projeyi bilgisayarınıza klonlayın veya indirin:
   ```bash
   git clone https://github.com/emrKvn0/Velo.git
   cd spotify-skipper
   ```
2. Gerekli kütüphaneleri yükleyin:
   ```bash
   pip install -r requirements.txt
   ```
3. Uygulamayı çalıştırın:
   ```bash
   python main.py
   ```

### 🖱️ Nasıl Kullanılır?

* **Sonraki Şarkı (Next Track):** Ekranın **sağ** kenarına doğru farenizi hızlıca ve hafif kavisli (sağ aşağı doğru) hareket ettirin.
* **Önceki Şarkı (Previous Track):** Ekranın **sol** kenarına doğru farenizi hızlıca ve hafif kavisli (sol aşağı doğru) hareket ettirin.
* Eğer uygulamadan **"Güvenlik Kilidi"** aktifse, farenizi hareket ettirirken klavyenizdeki **Sol CTRL** tuşuna basılı tutmanız gerekmektedir.


<br><hr><br>

<h2 id="english">🇬🇧 English</h2>

**Spotify Skipper** is a lightweight, modern Windows background utility that sits in your system tray and allows you to skip tracks on Spotify, YouTube, or other media players using mouse gestures (swoop/swipe movements).

### ✨ Features

* **Gesture Control:** Skip forward or backward by rapidly swiping your mouse in a curved motion towards the left or right edges of your screen.
* **Security Lock:** Prevent accidental skips! When enabled, gestures will only be recognized while you hold down the **Left CTRL** key.
* **System Tray Integration:** Runs seamlessly in the background. Hiding/closing the window minimizes it to your system tray.
* **Run on Startup:** Option to launch the application silently (without a console window) when Windows boots up, writing securely to the system registry.
* **Modern UI:** A clean, intuitive, and minimalist control panel built with PySide6.

### 🛠️ Installation & Requirements

* **OS:** Windows
* **Python Version:** Python 3.x

1. Clone or download the repository to your local machine:
   ```bash
   git clone https://github.com/emrKvn0/Velo.git
   cd spotify-skipper
   ```
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python main.py
   ```

### 🖱️ How to Use?

* **Next Track:** Swipe your mouse quickly with a slight downward curve towards the **right** edge of the screen.
* **Previous Track:** Swipe your mouse quickly with a slight downward curve towards the **left** edge of the screen.
* If the **"Security Lock"** is enabled in the UI settings, you must hold down the **Left CTRL** key on your keyboard while performing the mouse gesture.
