# Hand Motion Control Game 🎮🖐️

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.x-green)](https://opencv.org/)
[![MediaPipe](https://img.shields.io/badge/MediaPipe-0.8.x-orange)](https://google.github.io/mediapipe/)

---

## 📌 Tentang Proyek

**Hand Motion Control Game** adalah sebuah permainan interaktif berbasis pengenalan gesture tangan secara real-time menggunakan webcam.  
Permainan ini menggabungkan teknologi pengolahan citra dari **MediaPipe**, **OpenCV**, dan pemrograman multimedia Python untuk menghadirkan pengalaman bermain yang unik dan edukatif.

Proyek ini dibuat sebagai tugas akhir mata kuliah Sistem / Teknologi Multimedia (IF4021) di Program Studi Teknik Informatika ITERA 2024/2025.

---

## 🎯 Fitur Utama

- 🎥 Deteksi gesture tangan secara real-time menggunakan webcam.
- ✋ Kendali permainan menggunakan pose tangan seperti Open Hand, Peace, Metal, Fist, dan Pointing.
- 🚧 Rintangan bergerak diagonal yang harus dikoreksi dengan gesture yang benar.
- 🎵 Audio feedback untuk berbagai aksi, seperti sukses, peringatan, dan game over.
- 🎮 Gameplay yang menantang dengan sistem retry saat gesture salah.
- 🖼️ Tampilan grafis dengan efek glow pada rintangan dan animasi interaktif.

---

## 🚀 Demo Screenshot

![Screenshot Gameplay](link-gambar-screenshot.jpg)  
*Gambar di atas adalah contoh tampilan permainan saat dijalankan.*

---

## 🛠️ Instalasi dan Persiapan

1. **Clone repository ini:**

    ```bash
    git clone https://github.com/ericsonchandra99/Hand_Motion_Control_Game.git
    cd Hand_Motion_Control_Game
    ```

2. **Buat virtual environment (opsional tapi disarankan):**

    ```bash
    python -m venv venv
    source venv/bin/activate   # Linux/Mac
    venv\Scripts\activate      # Windows
    ```

3. **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

4. **Jalankan game:**

    ```bash
    python main.py
    ```

---

## 📖 Cara Bermain

- Saat permainan berjalan, kamu akan melihat rintangan dengan simbol gesture tertentu bergerak secara diagonal.
- Tempatkan tangan kamu dalam zona deteksi yang ditandai kotak berwarna oranye.
- Tunjukkan pose tangan yang sesuai dengan simbol rintangan saat rintangan masuk zona deteksi.
- Jika pose benar, kamu akan mendapat poin dan rintangan hilang.
- Jika salah, kamu harus mengoreksi pose sebelum rintangan bergerak keluar zona.
- Game berakhir saat gagal melewati rintangan atau gagal koreksi pose.

---

## 🧩 Struktur Kode Utama

- **`main.py`** — Program utama yang menjalankan game dan webcam.
- Fungsi `detect_gesture()` — Mendeteksi pose tangan berdasarkan landmark MediaPipe.
- Fungsi `create_obstacle()` — Membuat rintangan baru dengan gesture acak.
- Fungsi `draw_pose_obstacle()` — Menggambar rintangan dengan efek glow dan emoji.
- Game loop mengelola pergerakan rintangan, pengecekan gesture, skor, dan status game.

---

## ⚙️ Penjelasan Teknologi

| Teknologi    | Deskripsi                                   |
|--------------|---------------------------------------------|
| OpenCV       | Pengolahan video dan gambar secara real-time|
| MediaPipe    | Library deteksi pose dan landmark tangan     |
| Pillow (PIL) | Menggambar emoji di atas frame video          |
| winsound/playsound | Mengeluarkan suara feedback sesuai aksi |

---

## 📂 Struktur Folder



---

## 👥 Anggota Kelompok

| Nama Lengkap       | NIM       | GitHub                                      |
|--------------------|-----------|---------------------------------------------|
| Ericson Chandra    | 121450026 | [ericsonchandra99](https://github.com/ericsonchandra99)  |
| Nama Anggota 2     | 121450087 | [username2](https://github.com/username2)   |
| Kharisma Gumilang  | 121450142 | [gumilangkharismaa](https://github.com/gumilangkharismaa) |

---

## 📞 Kontak

- Ericson Chandra: [github.com/ericsonchandra99](https://github.com/ericsonchandra99)
- Kharisma Gumilang: [github.com/gumilangkharismaa](https://github.com/gumilangkharismaa)

---


