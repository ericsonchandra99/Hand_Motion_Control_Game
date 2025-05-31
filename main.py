import cv2  # library OpenCV untuk manipulasi gambar dan kamera
import mediapipe as mp  # library Mediapipe untuk deteksi tangan
import numpy as np  # library untuk operasi numerik dan array
import time  # library untuk waktu dan delay
import random  # library untuk fungsi acak
import pygame  # library untuk audio dan suara
import os  # library untuk operasi file dan direktori

# =========================
# BAGIAN INISIALISASI AUDIO
# =========================

def initialize_pygame_audio():
    pygame.mixer.init()  # mulai sistem audio pygame
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # dapatkan folder script saat ini
    resource_dir = os.path.join(BASE_DIR, "resources")  # folder 'resources' untuk suara dan gambar

    try:
        # load musik latar dan suara efek
        pygame.mixer.music.load(os.path.join(resource_dir, "stecu.wav"))
        sounds = {
            'score': pygame.mixer.Sound(os.path.join(resource_dir, "score.mp3")),
            'warning': pygame.mixer.Sound(os.path.join(resource_dir, "beep-warning-6387.mp3")),
            'gameover': pygame.mixer.Sound(os.path.join(resource_dir, "game-over-arcade-6435.mp3"))
        }
    except Exception as e:
        print(f"Error loading sounds: {e}")  # kalau error tampilkan
        sounds = {'score': None, 'warning': None, 'gameover': None}

    pygame.mixer.music.set_volume(0.3)  # set volume musik latar
    return sounds  # kembalikan objek suara

# =========================
# KONSTANTA DAN GLOBAL VARIABLES
# =========================

OBSTACLE_SIZE = 100  # ukuran obstacle (emoji) dalam pixel
INITIAL_OBSTACLE_SPEED_X = 7  # kecepatan awal obstacle ke kiri (x)
INITIAL_OBSTACLE_SPEED_Y = 4  # kecepatan awal obstacle ke atas (y)
SPEED_INCREASE_FACTOR_X = 0.15  # kenaikan kecepatan X tiap kenaikan skor
SPEED_INCREASE_FACTOR_Y = 0.075  # kenaikan kecepatan Y tiap kenaikan skor
SCORE_INCREASE_INTERVAL = 2  # setiap skor kelipatan 2, kecepatan naik

MAX_FAILS = 3  # batas maksimal kesalahan sebelum game over

# Posisi zona deteksi dalam rasio dari ukuran frame
DETECTION_ZONE_X_START_RATIO = 0.3
DETECTION_ZONE_X_END_RATIO = 0.7
DETECTION_ZONE_Y_START_RATIO = 0.2
DETECTION_ZONE_Y_END_RATIO = 0.8

# Kecepatan saat mode retry (koreksi)
RETRY_RETREAT_SPEED_X = 5.0
RETRY_RETREAT_SPEED_Y = 3.0
RETRY_ADVANCE_SPEED_X = 5.0
RETRY_ADVANCE_SPEED_Y = 3.0

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # direktori utama program
RESOURCE_DIR = os.path.join(BASE_DIR, "resources")  # folder sumber daya

# Daftar jenis obstacle (gesture dan gambar)
OBSTACLE_TYPES = [
    {'gesture': "Open Hand 🖐", 'image_path': os.path.join(RESOURCE_DIR, "open hand.png")},
    {'gesture': "Peace ✌", 'image_path': os.path.join(RESOURCE_DIR, "peace.png")},
    {'gesture': "Metal 🤘", 'image_path': os.path.join(RESOURCE_DIR, "metal.png")},
    {'gesture': "Fist ✊", 'image_path': os.path.join(RESOURCE_DIR, "fist.png")},
    {'gesture': "Pointing 👆", 'image_path': os.path.join(RESOURCE_DIR, "pointing.png")},
]

# Beberapa lelucon untuk layar game over
JOKES = [
    "Kenapa programmer selalu bingung di kamar mandi? Karena gak bisa menemukan bug!",
    "Mengapa komputer suka panas? Karena banyak cache!",
    "Kalau kamu merasa gagal, ingat: 'Segala sesuatu butuh debugging!'",
    "Kenapa keyboard selalu dingin? Karena banyak tombol Ctrl!",
    "Saya tidak malas, saya cuma optimasi waktu."
]

# Status game
STATE_MENU = 0
STATE_INSTRUCTIONS = 1
STATE_PLAYING = 2
STATE_GAMEOVER = 3

# =========================
# FUNGSI BANTU UMUM
# =========================

def play_sound(sound):
    if sound:  # kalau ada suara
        sound.play()  # mainkan suara

# Fungsi menggambar teks dengan outline supaya jelas
def draw_text_with_outline(img, text, pos, font_face, font_scale, text_color, thickness,
                           outline_color=(0, 0, 0), outline_thickness=2):
    x, y = pos
    # gambar outline di sekitar teks
    offsets = [
        (-outline_thickness, 0), (outline_thickness, 0), (0, -outline_thickness), (0, outline_thickness),
        (-outline_thickness, -outline_thickness), (outline_thickness, outline_thickness),
        (-outline_thickness, outline_thickness), (outline_thickness, -outline_thickness)
    ]
    for dx, dy in offsets:
        cv2.putText(img, text, (x + dx, y + dy), font_face, font_scale, outline_color, thickness)
    # gambar teks utama
    cv2.putText(img, text, pos, font_face, font_scale, text_color, thickness)

# Fungsi menggambar tombol dengan warna dan teks
def draw_button(img, text, x, y, w, h, bg_color, border_color, text_color, font_scale=1):
    overlay = img.copy()
    # gambar kotak background tombol
    cv2.rectangle(overlay, (x, y), (x + w, y + h), bg_color, -1)
    cv2.addWeighted(overlay, 0.9, img, 0.1, 0, img)
    # gambar border tombol
    cv2.rectangle(img, (x, y), (x + w, y + h), border_color, 3)

    # hitung posisi teks supaya di tengah tombol
    text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, font_scale, 2)[0]
    text_x = x + (w - text_size[0]) // 2
    text_y = y + (h + text_size[1]) // 2 - 5
    cv2.putText(img, text, (text_x, text_y), cv2.FONT_HERSHEY_DUPLEX, font_scale, text_color, 2)

# Cek apakah posisi mouse klik di dalam tombol
def is_click_on_button(x, y, btn_x, btn_y, btn_w, btn_h):
    return btn_x <= x <= btn_x + btn_w and btn_y <= y <= btn_y + btn_h

# Fungsi gambar obstacle emoji di posisi tertentu
def draw_pose_obstacle(img, obs_data):
    x, y = int(obs_data['x']), int(obs_data['y'])
    image_path = obs_data['image_path']

    emoji_img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)  # baca gambar emoji termasuk transparan

    if emoji_img is None:
        print(f"Error: Gambar tidak ditemukan di {image_path}")
        return

    emoji_img = cv2.resize(emoji_img, (OBSTACLE_SIZE, OBSTACLE_SIZE), interpolation=cv2.INTER_AREA)

    img_h, img_w = img.shape[:2]

    # batas crop supaya tidak keluar frame
    y1 = max(0, y)
    y2 = min(img_h, y + OBSTACLE_SIZE)
    x1 = max(0, x)
    x2 = min(img_w, x + OBSTACLE_SIZE)

    if y1 >= y2 or x1 >= x2:
        return

    # crop bagian emoji yang masuk dalam frame
    emoji_y1 = y1 - y
    emoji_y2 = emoji_y1 + (y2 - y1)
    emoji_x1 = x1 - x
    emoji_x2 = emoji_x1 + (x2 - x1)

    emoji_crop = emoji_img[emoji_y1:emoji_y2, emoji_x1:emoji_x2]

    # kalau ada channel alpha (transparansi)
    if emoji_crop.shape[2] == 4:
        alpha_s = emoji_crop[:, :, 3] / 255.0
        alpha_l = 1.0 - alpha_s

        # campur pixel gambar emoji dan background frame sesuai alpha
        for c in range(3):
            img[y1:y2, x1:x2, c] = (
                alpha_s * emoji_crop[:, :, c] + alpha_l * img[y1:y2, x1:x2, c]
            )
    else:
        # kalau tidak transparan langsung tempel
        img[y1:y2, x1:x2] = emoji_crop

# Buat obstacle baru secara acak jenisnya
def create_obstacle(frame_width, frame_height, obstacle_id):
    chosen_type = random.choice(OBSTACLE_TYPES)  # pilih emoji dan gesture acak
    start_x = frame_width - OBSTACLE_SIZE  # mulai dari kanan frame
    start_y = frame_height - OBSTACLE_SIZE - random.randint(50, 150)  # posisi y acak di bawah
    return {
        'id': obstacle_id,
        'x': float(start_x),
        'y': float(start_y),
        'required_gesture': chosen_type['gesture'],
        'image_path': chosen_type['image_path'],
        'passed': False  # obstacle belum dilewati
    }

# =========================
# LOGIKA PENDETEKSI GESTURE TANGAN
# =========================

def detect_gesture(landmarks):
    mp_hands = mp.solutions.hands

    # titik ujung jari dan sendi tengahnya
    finger_tips = [
        mp_hands.HandLandmark.THUMB_TIP, mp_hands.HandLandmark.INDEX_FINGER_TIP,
        mp_hands.HandLandmark.MIDDLE_FINGER_TIP, mp_hands.HandLandmark.RING_FINGER_TIP,
        mp_hands.HandLandmark.PINKY_TIP
    ]
    finger_pips = [
        mp_hands.HandLandmark.THUMB_IP, mp_hands.HandLandmark.INDEX_FINGER_PIP,
        mp_hands.HandLandmark.MIDDLE_FINGER_PIP, mp_hands.HandLandmark.RING_FINGER_PIP,
        mp_hands.HandLandmark.PINKY_PIP
    ]

    # cek jari terbuka/tutup berdasarkan posisi landmark y
    def is_finger_extended(tip_idx, pip_idx):
        return landmarks[tip_idx].y < landmarks[pip_idx].y + 0.02

    def is_finger_bent(tip_idx, pip_idx):
        return landmarks[tip_idx].y > landmarks[pip_idx].y - 0.02

    # cek ibu jari terbuka secara umum
    def is_thumb_open_general():
        thumb_x_dist = abs(landmarks[mp_hands.HandLandmark.THUMB_TIP].x - landmarks[mp_hands.HandLandmark.THUMB_MCP].x)
        thumb_y_pos_check = landmarks[mp_hands.HandLandmark.THUMB_TIP].y < landmarks[mp_hands.HandLandmark.THUMB_IP].y + 0.03
        return thumb_x_dist > 0.005 and thumb_y_pos_check

    # kondisi jari telunjuk menunjuk ke atas, jari lain menutup, ibu jari dekat
    index_pointing_up = (
        landmarks[mp_hands.HandLandmark.INDEX_FINGER_TIP].y < landmarks[mp_hands.HandLandmark.INDEX_FINGER_PIP].y and
        landmarks[mp_hands.HandLandmark.INDEX_FINGER_PIP].y < landmarks[mp_hands.HandLandmark.INDEX_FINGER_MCP].y
    )
    other_fingers_bent = (
        is_finger_bent(finger_tips[2], finger_pips[2]) and
        is_finger_bent(finger_tips[3], finger_pips[3]) and
        is_finger_bent(finger_tips[4], finger_pips[4])
    )
    thumb_pointing_pos = abs(landmarks[mp_hands.HandLandmark.THUMB_TIP].x - landmarks[mp_hands.HandLandmark.INDEX_FINGER_MCP].x) < 0.2

    # kembalikan nama gesture sesuai pola di atas
    if index_pointing_up and other_fingers_bent and thumb_pointing_pos:
        return "Pointing 👆"

    # cek gesture Peace
    peace_thumb_check = abs(landmarks[mp_hands.HandLandmark.THUMB_TIP].x - landmarks[mp_hands.HandLandmark.THUMB_IP].x) > 0.005
    if (is_finger_extended(finger_tips[1], finger_pips[1]) and
            is_finger_extended(finger_tips[2], finger_pips[2]) and
            is_finger_bent(finger_tips[3], finger_pips[3]) and
            is_finger_bent(finger_tips[4], finger_pips[4]) and
            peace_thumb_check):
        return "Peace ✌"

    # cek gesture Metal
    if (is_finger_extended(finger_tips[1], finger_pips[1]) and
            is_finger_bent(finger_tips[2], finger_pips[2]) and
            is_finger_bent(finger_tips[3], finger_pips[3]) and
            is_finger_extended(finger_tips[4], finger_pips[4]) and
            is_thumb_open_general()):
        return "Metal 🤘"

    # cek gesture Open Hand
    if (is_finger_extended(finger_tips[1], finger_pips[1]) and
            is_finger_extended(finger_tips[2], finger_pips[2]) and
            is_finger_extended(finger_tips[3], finger_pips[3]) and
            is_finger_extended(finger_tips[4], finger_pips[4]) and
            is_thumb_open_general()):
        return "Open Hand 🖐"

    # cek gesture Fist (tangan mengepal)
    all_fingers_bent = (
        is_finger_bent(finger_tips[1], finger_pips[1]) and
        is_finger_bent(finger_tips[2], finger_pips[2]) and
        is_finger_bent(finger_tips[3], finger_pips[3]) and
        is_finger_bent(finger_tips[4], finger_pips[4])
    )
    if all_fingers_bent and not is_thumb_open_general():
        return "Fist ✊"

    return "Unknown"  # kalau gesture tidak dikenali

# =========================
# EVENT HANDLE MOUSE
# =========================

mouse_clicked = False
mouse_x, mouse_y = -1, -1

def mouse_callback(event, x, y, flags, param):
    global mouse_clicked, mouse_x, mouse_y
    if event == cv2.EVENT_LBUTTONDOWN:  # kalau klik kiri mouse
        mouse_clicked = True  # catat klik
        mouse_x, mouse_y = x, y  # simpan posisi klik

# =========================
# GAMBARAN ANTARMUKA (UI)
# =========================

def draw_detection_zone(img, width, height):
    # gambar kotak transparan zona deteksi gesture tangan
    x_start = int(width * DETECTION_ZONE_X_START_RATIO)
    x_end = int(width * DETECTION_ZONE_X_END_RATIO)
    y_start = int(height * DETECTION_ZONE_Y_START_RATIO)
    y_end = int(height * DETECTION_ZONE_Y_END_RATIO)

    # buat efek warna dan ketebalan berdenyut supaya menarik
    pulse_thickness = 4 + int(3 * abs(np.sin(time.time() * 5)))
    pulse_value = int(150 + 105 * abs(np.sin(time.time() * 3)))
    color = (pulse_value, pulse_value, 255)

    overlay = img.copy()
    alpha = 0.2  # transparansi
    cv2.rectangle(overlay, (x_start, y_start), (x_end, y_end), color, -1)
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)
    cv2.rectangle(img, (x_start, y_start), (x_end, y_end), color, pulse_thickness)

    font = cv2.FONT_HERSHEY_SIMPLEX
    text = "Zona Deteksi"
    sz = cv2.getTextSize(text, font, 1, 2)[0]
    tx = x_start + (x_end - x_start - sz[0]) // 2
    ty = y_start + sz[1] + 15
    cv2.putText(img, text, (tx + 3, ty + 3), font, 1, (0, 0, 0), 5)  # shadow hitam
    cv2.putText(img, text, (tx, ty), font, 1, color, 3)  # teks utama

def draw_hud_panel(img, width, height):
    # gambar panel info skor dan gagal di atas frame
    panel_height = 110
    overlay = img.copy()
    cv2.rectangle(overlay, (0, 0), (width, panel_height), (15, 15, 30), -1)
    alpha = 0.7
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)
    cv2.line(img, (0, panel_height), (width, panel_height), (80, 80, 120), 2)

def render_menu_screen(img, w, h, btn_start_x, btn_start_y, btn_instruction_y, btn_exit_x, btn_exit_y, btn_w, btn_h):
    # gambar layar menu utama
    overlay = img.copy()
    cv2.rectangle(overlay, (0, 0), (w, h), (10, 10, 40), -1)
    cv2.addWeighted(overlay, 0.85, img, 0.15, 0, img)

    title = "Gesture Diagonal Obstacle Game"
    font = cv2.FONT_HERSHEY_DUPLEX
    font_scale = 1.2
    thickness = 6

    (text_width, _), _ = cv2.getTextSize(title, font, font_scale, thickness)
    x = (w - text_width) // 2
    y = h // 2 - 200
    draw_text_with_outline(img, title, (x, y), font, font_scale, (255, 255, 255), thickness)

    # tombol mulai, cara main, keluar
    draw_button(img, "Mulai Game", btn_start_x, btn_start_y, btn_w, btn_h,
                (70, 130, 220), (255, 255, 255), (255, 255, 255), 1.2)
    draw_button(img, "Cara Main", btn_start_x, btn_instruction_y, btn_w, btn_h,
                (120, 180, 90), (255, 255, 255), (255, 255, 255), 1.2)
    draw_button(img, "Keluar", btn_exit_x, btn_exit_y, btn_w, btn_h,
                (220, 70, 70), (255, 255, 255), (255, 255, 255), 1.2)

def render_instructions_screen(img, w, h, btn_start_x, btn_w, btn_h):
    # layar cara main game
    overlay = img.copy()
    cv2.rectangle(overlay, (0, 0), (w, h), (10, 10, 40), -1)
    cv2.addWeighted(overlay, 0.85, img, 0.15, 0, img)

    title = "Cara Main"
    font = cv2.FONT_HERSHEY_DUPLEX
    font_scale = 1.4
    thickness = 6

    (text_width, _), _ = cv2.getTextSize(title, font, font_scale, thickness)
    x = (w - text_width) // 2
    y = 100
    draw_text_with_outline(img, title, (x, y), font, font_scale, (255, 255, 255), thickness)

    instructions = [
        "1. Gerakkan tangan di area Zona Deteksi.",
        "2. Cocokkan gesture tangan dengan emoji obstacle.",
        "3. Gesture yang benar akan menambah skor.",
        "4. Jika salah gesture atau tangan tidak di zona,",
        "   harus koreksi pose pada obstacle yang sama.",
        "5. Maksimal 3 kali gagal, maka game over.",
        "6. Tekan tombol ESC untuk keluar kapan saja."
    ]

    font_scale_ins = 0.9
    thickness_ins = 2
    start_y = y + 80
    line_height = 40

    # tulis instruksi satu per satu di layar
    for i, line in enumerate(instructions):
        draw_text_with_outline(img, line, (50, start_y + i * line_height),
                               cv2.FONT_HERSHEY_SIMPLEX, font_scale_ins, (255, 255, 255), thickness_ins)

    # tombol kembali ke menu
    draw_button(img, "Kembali", btn_start_x, w - 120, btn_w, btn_h,
                (70, 130, 220), (255, 255, 255), (255, 255, 255), 1.2)

def render_game_info(img, w, h, score, fails, max_fails, hand_detected, player_gesture,
                     speed_x, speed_y, in_retry_mode, obstacles, stalled_id, stalled_state, sounds):
    # tampilkan skor, gagal, status tangan, kecepatan, dan mode koreksi
    pulse_val = int(200 + 55 * abs(np.sin(time.time() * 3)))
    pulse_color = (pulse_val, 255, pulse_val)
    draw_text_with_outline(img, f"SKOR: {score}", (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 1.2, pulse_color, 4)
    draw_text_with_outline(img, f"Gagal: {fails}/{max_fails}", (w - 280, 70), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 180, 255), 4)

    if hand_detected:
        draw_text_with_outline(img, f"Tangan: {player_gesture} ✅", (20, h - 70), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
    else:
        draw_text_with_outline(img, "Gerakkan Tangan Anda", (20, h - 70), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 165, 255), 3)

    draw_text_with_outline(img, f"Kecepatan: X={speed_x:.1f} Y={speed_y:.1f}", (20, h - 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)

    if in_retry_mode:
        retry_msg = "KOREKSI POSE!"
        draw_text_with_outline(img, retry_msg, (w // 2 - 120, h // 2 - 120), cv2.FONT_HERSHEY_DUPLEX, 1.4, (0, 165, 255), 4)
        if obstacles and obstacles[0]['id'] == stalled_id:
            draw_text_with_outline(img, f"Pose: {obstacles[0]['required_gesture']}", (w // 2 - 180, h // 2 - 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 3)
        draw_text_with_outline(img, f"Gesture Anda: {player_gesture}", (w // 2 - 140, h // 2 - 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 3)
        draw_text_with_outline(img, f"Status: {stalled_state.replace('_', ' ').title()}", (w // 2 - 170, h // 2 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

def render_gameover_screen(img, w, h, score, jokes, joke_idx, joke_timer, btn_restart_x, btn_restart_y, btn_exit_x, btn_exit_y, btn_w, btn_h):
    # gambar layar game over dengan skor dan lelucon
    overlay = img.copy()
    cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.75, img, 0.25, 0, img)

    draw_text_with_outline(img, "GAME OVER!", (w // 2 - 180, h // 2 - 120), cv2.FONT_HERSHEY_DUPLEX, 2, (0, 0, 255), 5)
    draw_text_with_outline(img, f"SKOR AKHIR: {score}", (w // 2 - 160, h // 2 - 50), cv2.FONT_HERSHEY_DUPLEX, 1.3, (255, 255, 255), 4)

    # atur pergantian lelucon setiap 4 detik
    current_time = int(time.time() * 1000)
    if joke_timer == 0:
        joke_timer = current_time
        joke_idx = 0
    elif current_time - joke_timer > 4000:
        joke_timer = current_time
        joke_idx = (joke_idx + 1) % len(jokes)

    joke_text = jokes[joke_idx]
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.7
    thickness = 2
    (joke_width, joke_height), _ = cv2.getTextSize(joke_text, font, font_scale, thickness)
    x = (w - joke_width) // 2
    y = (h + joke_height) // 2
    draw_text_with_outline(img, joke_text, (x, y), font, font_scale, (255, 255, 255), thickness)

    # tombol mulai ulang dan keluar
    draw_button(img, "Mulai Ulang", btn_restart_x, btn_restart_y, btn_w, btn_h,
                (70, 130, 220), (255, 255, 255), (255, 255, 255), 1.2)
    draw_button(img, "Keluar", btn_exit_x, btn_exit_y, btn_w, btn_h,
                (220, 70, 70), (255, 255, 255), (255, 255, 255), 1.2)

    return joke_idx, joke_timer

# =========================
# FUNGSI UTAMA GAMEPLAY LOOP
# =========================

def run_gameplay_loop(img, w, h, obstacles, obstacle_counter,
                      hand_detected, hand_x, hand_y, player_gesture,
                      score, fails, retry_fails, last_failed_obstacle_id,
                      in_retry_mode, stalled_obstacle_id, stalled_reason,
                      stalled_obstacle_state, current_speed_x, current_speed_y, sounds):
    # hitung posisi zona deteksi berdasarkan ukuran layar
    det_zone_x_start = int(w * DETECTION_ZONE_X_START_RATIO)
    det_zone_x_end = int(w * DETECTION_ZONE_X_END_RATIO)
    det_zone_y_start = int(h * DETECTION_ZONE_Y_START_RATIO)
    det_zone_y_end = int(h * DETECTION_ZONE_Y_END_RATIO)

    # proses setiap obstacle (emoji) yang ada
    for obs in obstacles:
        # kalau sedang mode koreksi dan obstacle ini yang gagal
        if in_retry_mode and obs['id'] == stalled_obstacle_id:
            if stalled_obstacle_state == 'retreating':  # obstacle mundur untuk beri waktu koreksi
                obs['x'] += RETRY_RETREAT_SPEED_X
                obs['y'] += RETRY_RETREAT_SPEED_Y
                # jika sudah mundur cukup jauh
                if obs['x'] > det_zone_x_end + OBSTACLE_SIZE / 2:
                    stalled_obstacle_state = 'advancing_for_retry'  # maju lagi ke zona deteksi
                    play_sound(sounds['warning'])
            elif stalled_obstacle_state == 'advancing_for_retry':
                obs['x'] -= RETRY_ADVANCE_SPEED_X
                obs['y'] -= RETRY_ADVANCE_SPEED_Y
                # kalau obstacle sudah masuk zona deteksi
                if (det_zone_x_start < obs['x'] + OBSTACLE_SIZE / 2 < det_zone_x_end and
                        det_zone_y_start < obs['y'] + OBSTACLE_SIZE / 2 < det_zone_y_end):
                    stalled_obstacle_state = 'waiting_for_correction'  # tunggu koreksi gesture
                    play_sound(sounds['gameover'])
        else:
            # obstacle bergerak maju normal sesuai kecepatan
            obs['x'] -= current_speed_x
            obs['y'] -= current_speed_y

        # gambar obstacle di layar
        draw_pose_obstacle(img, obs)

        # cek apakah obstacle berada di zona deteksi
        is_in_detection_zone = (det_zone_x_start < obs['x'] + OBSTACLE_SIZE // 2 < det_zone_x_end and
                                det_zone_y_start < obs['y'] + OBSTACLE_SIZE // 2 < det_zone_y_end)

        # kalau obstacle di zona dan belum dilewati
        if is_in_detection_zone and not obs['passed']:
            if hand_detected:  # kalau tangan terdeteksi
                # cek apakah tangan di dalam zona
                is_hand_in_zone = (det_zone_x_start < hand_x < det_zone_x_end and
                                   det_zone_y_start < hand_y < det_zone_y_end)
                if is_hand_in_zone:
                    # cek gesture yang dikenali sama dengan yang obstacle minta
                    if player_gesture == obs['required_gesture']:
                        # kalau mode koreksi dan obstacle ini yg gagal
                        if in_retry_mode and obs['id'] == stalled_obstacle_id:
                            # koreksi berhasil, reset mode retry
                            in_retry_mode = False
                            stalled_obstacle_id = -1
                            stalled_reason = ""
                            stalled_obstacle_state = ''
                            retry_fails = 0
                            last_failed_obstacle_id = None
                            play_sound(sounds['gameover'])
                        if not obs['passed']:
                            obs['passed'] = True  # obstacle berhasil dilewati
                            score += 1  # tambah skor
                            play_sound(sounds['score'])
                            # tiap interval skor tertentu, tingkatkan kecepatan obstacle
                            if score % SCORE_INCREASE_INTERVAL == 0:
                                current_speed_x += SPEED_INCREASE_FACTOR_X
                                current_speed_y += SPEED_INCREASE_FACTOR_Y
                    else:
                        # gesture salah, aktifkan mode retry
                        if not in_retry_mode:
                            in_retry_mode = True
                            stalled_obstacle_id = obs['id']
                            stalled_reason = "wrong_gesture"
                            stalled_obstacle_state = 'retreating'
                            # hitung gagal berturut-turut di obstacle yang sama
                            if last_failed_obstacle_id == stalled_obstacle_id:
                                retry_fails += 1
                            else:
                                retry_fails = 1
                                last_failed_obstacle_id = stalled_obstacle_id
                            fails += 1
                            play_sound(sounds['warning'])
                else:
                    # tangan tidak di zona deteksi, juga mode retry
                    if not in_retry_mode:
                        in_retry_mode = True
                        stalled_obstacle_id = obs['id']
                        stalled_reason = "hand_not_in_zone"
                        stalled_obstacle_state = 'retreating'
                        if last_failed_obstacle_id == stalled_obstacle_id:
                            retry_fails += 1
                        else:
                            retry_fails = 1
                            last_failed_obstacle_id = stalled_obstacle_id
                        fails += 1
                        play_sound(sounds['warning'])
            else:
                # tidak ada tangan terdeteksi, mode retry juga
                if not in_retry_mode:
                    in_retry_mode = True
                    stalled_obstacle_id = obs['id']
                    stalled_reason = "no_hand_detected"
                    stalled_obstacle_state = 'retreating'
                    if last_failed_obstacle_id == stalled_obstacle_id:
                        retry_fails += 1
                    else:
                        retry_fails = 1
                        last_failed_obstacle_id = stalled_obstacle_id
                    fails += 1
                    play_sound(sounds['warning'])

        # kalau gagal terlalu banyak, game over
        if fails >= MAX_FAILS or retry_fails >= MAX_FAILS:
            pygame.mixer.music.stop()
            play_sound(sounds['gameover'])
            return STATE_GAMEOVER, score, fails, retry_fails, last_failed_obstacle_id, in_retry_mode, stalled_obstacle_id, stalled_reason, stalled_obstacle_state, obstacles, obstacle_counter, current_speed_x, current_speed_y

        # kalau mode retry dan obstacle gagal sudah melewati zona deteksi
        if in_retry_mode and obs['id'] == stalled_obstacle_id:
            if ((obs['x'] + OBSTACLE_SIZE // 2 < det_zone_x_start and stalled_obstacle_state == 'waiting_for_correction') or
                (obs['y'] + OBSTACLE_SIZE // 2 < det_zone_y_start and stalled_obstacle_state == 'waiting_for_correction') or
                (obs['x'] > w + OBSTACLE_SIZE)):
                fails += 1  # hitung gagal
                if fails >= MAX_FAILS:
                    pygame.mixer.music.stop()
                    play_sound(sounds['warning'])
                    return STATE_GAMEOVER, score, fails, retry_fails, last_failed_obstacle_id, in_retry_mode, stalled_obstacle_id, "failed_correction", stalled_obstacle_state, obstacles, obstacle_counter, current_speed_x, current_speed_y
                else:
                    stalled_obstacle_state = 'retreating'
                    play_sound(sounds['warning'])

        # kalau obstacle keluar layar dan belum dilewati, hitung gagal
        if (obs['x'] + OBSTACLE_SIZE < 0 or obs['y'] < 0) and not obs['passed']:
            if not in_retry_mode:
                fails += 1
                if fails >= MAX_FAILS:
                    pygame.mixer.music.stop()
                    play_sound(sounds['warning'])
                    return STATE_GAMEOVER, score, fails, retry_fails, last_failed_obstacle_id, in_retry_mode, stalled_obstacle_id, "missed_obstacle", stalled_obstacle_state, obstacles, obstacle_counter, current_speed_x, current_speed_y
                else:
                    play_sound(sounds['warning'])

    # buang obstacle yang sudah keluar layar kecuali obstacle gagal sedang koreksi
    obstacles = [obs for obs in obstacles if (obs['x'] + OBSTACLE_SIZE > 0 and obs['y'] + OBSTACLE_SIZE > 0) or
                 (stalled_obstacle_id == obs['id'])]

    # Buat obstacle baru kalau semua obstacle sudah dilewati dan tidak dalam mode retry
    if not in_retry_mode:
        unfinished = any(not obs['passed'] for obs in obstacles)
        if not unfinished:
            # buat obstacle baru kalau list kosong atau obstacle terakhir sudah cukup jauh dari kanan
            if len(obstacles) == 0 or (obstacles[-1]['x'] < w - 300 and obstacles[-1]['y'] < h - 300):
                obstacle_counter += 1
                obstacles.append(create_obstacle(w, h, obstacle_counter))

    # kembalikan semua variabel game untuk update di main loop
    return (STATE_PLAYING, score, fails, retry_fails, last_failed_obstacle_id,
            in_retry_mode, stalled_obstacle_id, stalled_reason, stalled_obstacle_state,
            obstacles, obstacle_counter, current_speed_x, current_speed_y)

# Fungsi reset game ke keadaan awal
def reset_game(w, h):
    return (
        STATE_PLAYING,  # status game mulai main
        0,  # skor awal 0
        0,  # gagal awal 0
        0,  # retry gagal awal 0
        None,  # belum ada obstacle gagal terakhir
        [create_obstacle(w, h, 0)],  # mulai dengan satu obstacle baru
        0,  # hitung obstacle mulai dari 0
        INITIAL_OBSTACLE_SPEED_X,  # kecepatan awal obstacle X
        INITIAL_OBSTACLE_SPEED_Y,  # kecepatan awal obstacle Y
        set(),  # set kosong (tidak dipakai di kode ini)
        False,  # tidak dalam mode retry
        -1,  # id obstacle gagal tidak ada
        "",  # alasan stalled kosong
        ''  # status stalled kosong
    )

# =========================
# MAIN GAME LOOP
# =========================

def main():
    cap = cv2.VideoCapture(0)  # buka kamera default
    if not cap.isOpened():
        print("Tidak dapat membuka kamera.")
        return

    width, height = 1280, 720
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)  # set ukuran frame kamera
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    window_name = "Gesture Diagonal Obstacle Game"
    cv2.namedWindow(window_name, cv2.WND_PROP_FULLSCREEN)  # buat window fullscreen
    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.setMouseCallback(window_name, mouse_callback)  # pasang fungsi callback mouse klik

    sounds = initialize_pygame_audio()  # inisialisasi suara

    mp_hands_module = mp.solutions.hands
    # setup detektor tangan
    hands_detector = mp_hands_module.Hands(max_num_hands=1, min_detection_confidence=0.7, min_tracking_confidence=0.7)
    mp_drawing = mp.solutions.drawing_utils
    mp_drawing_styles = mp.solutions.drawing_styles

    # inisialisasi variabel game
    game_state = STATE_MENU
    score = 0
    fails = 0
    retry_fails = 0
    last_failed_obstacle_id = None
    in_retry_mode = False
    stalled_obstacle_id = -1
    stalled_reason = ""
    stalled_obstacle_state = ''
    obstacles = []
    obstacle_counter = 0
    current_speed_x = INITIAL_OBSTACLE_SPEED_X
    current_speed_y = INITIAL_OBSTACLE_SPEED_Y
    passed_obstacle_ids = set()
    joke_index = 0
    joke_timer_start = 0

    # posisi tombol
    btn_w, btn_h = 240, 70
    btn_start_x = width // 2 - btn_w // 2
    btn_start_y = height // 2 - 120
    btn_instruction_y = height // 2 - 40
    btn_restart_x = btn_start_x
    btn_restart_y = height // 2 + 20
    btn_exit_x = btn_start_x
    btn_exit_y = height // 2 + 110

    pygame.mixer.music.play(-1)  # mulai mainkan musik latar loop terus

    global mouse_clicked, mouse_x, mouse_y

    while True:
        ret, frame = cap.read()  # baca frame dari kamera
        if not ret:
            print("Gagal membaca frame dari kamera.")
            break

        frame = cv2.flip(frame, 1)  # flip horizontal supaya seperti cermin
        img = frame.copy()  # buat salinan frame untuk gambar game

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)  # ubah ke RGB untuk Mediapipe
        hand_results = hands_detector.process(rgb_frame)  # deteksi tangan

        hand_detected = False
        hand_x, hand_y = -1, -1
        player_gesture = "Unknown"

        if hand_results.multi_hand_landmarks and game_state == STATE_PLAYING:
            for hand_landmarks in hand_results.multi_hand_landmarks:
                # gambar landmark tangan
                mp_drawing.draw_landmarks(
                    img, hand_landmarks, mp_hands_module.HAND_CONNECTIONS,
                    mp_drawing_styles.get_default_hand_landmarks_style(),
                    mp_drawing_styles.get_default_hand_connections_style())

                # ambil koordinat pergelangan tangan (wrist)
                hand_x = int(hand_landmarks.landmark[mp_hands_module.HandLandmark.WRIST].x * width)
                hand_y = int(hand_landmarks.landmark[mp_hands_module.HandLandmark.WRIST].y * height)
                hand_detected = True

                # deteksi gesture tangan
                player_gesture = detect_gesture(hand_landmarks.landmark)

                # gambar lingkaran pulse di pergelangan tangan
                pulse_radius = 15 + int(5 * abs(np.sin(time.time() * 8)))
                pulse_color_val = int(255 * abs(np.sin(time.time() * 4)))
                cv2.circle(img, (hand_x, hand_y), pulse_radius, (255, pulse_color_val, 255), -1)
                cv2.putText(img, "WRIST", (hand_x + 20, hand_y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 255), 2)

        # Tampilkan layar menu utama
        if game_state == STATE_MENU:
            render_menu_screen(img, width, height,
                               btn_start_x, btn_start_y,
                               btn_instruction_y, btn_exit_x, btn_exit_y,
                               btn_w, btn_h)

            # Cek klik tombol menu
            if mouse_clicked:
                if is_click_on_button(mouse_x, mouse_y, btn_start_x, btn_start_y, btn_w, btn_h):
                    # mulai game baru
                    (game_state, score, fails, retry_fails, last_failed_obstacle_id,
                     obstacles, obstacle_counter, current_speed_x, current_speed_y,
                     passed_obstacle_ids, in_retry_mode, stalled_obstacle_id,
                     stalled_reason, stalled_obstacle_state) = reset_game(width, height)
                    play_sound(sounds['gameover'])
                elif is_click_on_button(mouse_x, mouse_y, btn_start_x, btn_instruction_y, btn_w, btn_h):
                    game_state = STATE_INSTRUCTIONS  # buka layar cara main
                elif is_click_on_button(mouse_x, mouse_y, btn_exit_x, btn_exit_y, btn_w, btn_h):
                    break  # keluar game
                mouse_clicked = False

        # Tampilkan layar instruksi
        elif game_state == STATE_INSTRUCTIONS:
            render_instructions_screen(img, width, height, btn_start_x, btn_w, btn_h)

            # cek klik tombol kembali
            if mouse_clicked:
                if is_click_on_button(mouse_x, mouse_y, btn_start_x, height - 120, btn_w, btn_h):
                    game_state = STATE_MENU  # kembali ke menu utama
                mouse_clicked = False

        # Gameplay utama saat bermain
        elif game_state == STATE_PLAYING:
            # jalankan logika game utama
            (game_state, score, fails, retry_fails, last_failed_obstacle_id,
             in_retry_mode, stalled_obstacle_id, stalled_reason, stalled_obstacle_state,
             obstacles, obstacle_counter, current_speed_x, current_speed_y) = run_gameplay_loop(
                img, width, height, obstacles, obstacle_counter,
                hand_detected, hand_x, hand_y, player_gesture,
                score, fails, retry_fails, last_failed_obstacle_id,
                in_retry_mode, stalled_obstacle_id, stalled_reason,
                stalled_obstacle_state, current_speed_x, current_speed_y,
                sounds)

            # gambar zona deteksi dan panel HUD
            draw_detection_zone(img, width, height)
            draw_hud_panel(img, width, height)

            # tampilkan info game di layar
            render_game_info(img, width, height, score, fails, MAX_FAILS,
                             hand_detected, player_gesture,
                             current_speed_x, current_speed_y, in_retry_mode,
                             obstacles, stalled_obstacle_id, stalled_obstacle_state,
                             sounds)

        # Layar game over
        elif game_state == STATE_GAMEOVER:
            # tampilkan layar game over dan lelucon
            joke_index, joke_timer_start = render_gameover_screen(
                img, width, height, score, JOKES, joke_index, joke_timer_start,
                btn_restart_x, btn_restart_y, btn_exit_x, btn_exit_y, btn_w, btn_h)

            # cek klik tombol restart atau keluar
            if mouse_clicked:
                if is_click_on_button(mouse_x, mouse_y, btn_restart_x, btn_restart_y, btn_w, btn_h):
                    # reset game dan mulai musik
                    (game_state, score, fails, retry_fails, last_failed_obstacle_id,
                     obstacles, obstacle_counter, current_speed_x, current_speed_y,
                     passed_obstacle_ids, in_retry_mode, stalled_obstacle_id,
                     stalled_reason, stalled_obstacle_state) = reset_game(width, height)
                    pygame.mixer.music.play(-1)
                    play_sound(sounds['gameover'])
                elif is_click_on_button(mouse_x, mouse_y, btn_exit_x, btn_exit_y, btn_w, btn_h):
                    break  # keluar game
                mouse_clicked = False

        # tampilkan frame hasil rendering
        cv2.imshow(window_name, img)
        key = cv2.waitKey(10)
        if key == 27:  # ESC untuk keluar
            break

    # selesai game, stop musik dan tutup kamera serta window
    pygame.mixer.music.stop()
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()  # jalankan program utama
