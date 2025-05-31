import cv2
import mediapipe as mp
import numpy as np
import time
import platform
import random
from PIL import Image, ImageDraw, ImageFont
import pygame
import os

# =========================
# BAGIAN INISIALISASI
# =========================

def initialize_pygame_audio():
    # Inisialisasi mixer pygame untuk suara
    # Load musik latar dan efek suara dari folder resources
    pygame.mixer.init()
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # lokasi file skrip
    resource_dir = os.path.join(BASE_DIR, "resources")  # folder resources relatif

    try:
        # Load musik latar
        pygame.mixer.music.load(os.path.join(resource_dir, "videoplayback-_1_.wav"))
        # Load efek suara
        sounds = {
            'score': pygame.mixer.Sound(os.path.join(resource_dir, "score.mp3")),
            'warning': pygame.mixer.Sound(os.path.join(resource_dir, "beep-warning-6387.mp3")),
            'gameover': pygame.mixer.Sound(os.path.join(resource_dir, "game-over-arcade-6435.mp3"))
        }
    except Exception as e:
        print(f"Error loading sounds: {e}")
        sounds = {'score': None, 'warning': None, 'gameover': None}

    pygame.mixer.music.set_volume(0.3)  # atur volume musik latar
    return sounds

def load_emoji_font(size: int):
    # Mencari font emoji sesuai sistem operasi (Windows, macOS, Linux)
    # Jika gagal, pakai font default
    try:
        system = platform.system()
        if system == "Windows":
            font_path = "C:/Windows/Fonts/seguiemj.ttf"
        elif system == "Darwin":
            font_path = "/System/Library/Fonts/Apple Color Emoji.ttc"
        else:
            font_path = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
        return ImageFont.truetype(font_path, size)
    except Exception:
        return ImageFont.load_default()


# =========================
# KONSTANTA DAN VARIABEL GLOBAL
# =========================

OBSTACLE_SIZE = 100  # Ukuran kotak obstacle emoji
INITIAL_OBSTACLE_SPEED_X = 7  # Kecepatan obstacle bergerak horizontal (ke kiri)
INITIAL_OBSTACLE_SPEED_Y = 4  # Kecepatan obstacle bergerak vertikal (ke atas)
SPEED_INCREASE_FACTOR_X = 0.15  # Penambahan kecepatan per skor interval
SPEED_INCREASE_FACTOR_Y = 0.075

SCORE_INCREASE_INTERVAL = 5  # Setiap skor kelipatan ini, kecepatan naik

MAX_FAILS = 3  # Maksimal kesalahan sampai game over

# Rasio posisi zona deteksi tangan dalam frame kamera
DETECTION_ZONE_X_START_RATIO = 0.3
DETECTION_ZONE_X_END_RATIO = 0.7
DETECTION_ZONE_Y_START_RATIO = 0.2
DETECTION_ZONE_Y_END_RATIO = 0.8

# Kecepatan obstacle saat mode koreksi (retry)
RETRY_RETREAT_SPEED_X = 5.0
RETRY_RETREAT_SPEED_Y = 3.0
RETRY_ADVANCE_SPEED_X = 5.0
RETRY_ADVANCE_SPEED_Y = 3.0

# Daftar jenis gesture dan emoji obstacle
OBSTACLE_TYPES = [
    {'gesture': "Open Hand 🖐", 'emoji': "🖐"},
    {'gesture': "Peace ✌", 'emoji': "✌"},
    {'gesture': "Metal 🤘", 'emoji': "🤘"},
    {'gesture': "Fist ✊", 'emoji': "✊"},
    {'gesture': "Pointing 👆", 'emoji': "👆"},
]

# Jokes untuk ditampilkan saat game over
JOKES = [
    "Kenapa programmer selalu bingung di kamar mandi? Karena gak bisa menemukan bug!",
    "Mengapa komputer suka panas? Karena banyak cache!",
    "Kalau kamu merasa gagal, ingat: 'Segala sesuatu butuh debugging!'",
    "Kenapa keyboard selalu dingin? Karena banyak tombol Ctrl!",
    "Saya tidak malas, saya cuma optimasi waktu."
]

# Status game untuk memudahkan pengelolaan state
STATE_MENU = 0
STATE_INSTRUCTIONS = 1
STATE_PLAYING = 2
STATE_GAMEOVER = 3


# =========================
# FUNGSI BANTUAN UMUM
# =========================

def play_sound(sound):
    # Mainkan efek suara jika tersedia
    if sound:
        sound.play()

def draw_text_with_outline(img, text, pos, font_face, font_scale, text_color, thickness,
                           outline_color=(0, 0, 0), outline_thickness=2):
    # Menggambar teks dengan bayangan luar (outline) supaya lebih jelas terlihat
    x, y = pos
    offsets = [(-outline_thickness, 0), (outline_thickness, 0), (0, -outline_thickness), (0, outline_thickness),
               (-outline_thickness, -outline_thickness), (outline_thickness, outline_thickness),
               (-outline_thickness, outline_thickness), (outline_thickness, -outline_thickness)]
    for dx, dy in offsets:
        cv2.putText(img, text, (x + dx, y + dy), font_face, font_scale, outline_color, thickness)
    cv2.putText(img, text, pos, font_face, font_scale, text_color, thickness)

def draw_button(img, text, x, y, w, h, bg_color, border_color, text_color, font_scale=1):
    # Menggambar tombol persegi panjang dengan warna background, border, dan teks
    overlay = img.copy()
    cv2.rectangle(overlay, (x, y), (x + w, y + h), bg_color, -1)
    cv2.addWeighted(overlay, 0.9, img, 0.1, 0, img)
    cv2.rectangle(img, (x, y), (x + w, y + h), border_color, 3)

    text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, font_scale, 2)[0]
    text_x = x + (w - text_size[0]) // 2
    text_y = y + (h + text_size[1]) // 2 - 5
    cv2.putText(img, text, (text_x, text_y), cv2.FONT_HERSHEY_DUPLEX, font_scale, text_color, 2)

def is_click_on_button(x, y, btn_x, btn_y, btn_w, btn_h):
    # Cek apakah posisi klik mouse (x,y) ada di dalam tombol
    return btn_x <= x <= btn_x + btn_w and btn_y <= y <= btn_y + btn_h

def draw_pose_obstacle(img, obs_data, emoji_font):
    # Menggambar emoji obstacle pada posisi x,y dengan bantuan PIL agar emoji berwarna
    x, y = int(obs_data['x']), int(obs_data['y'])
    emoji = obs_data['emoji']

    pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)

    try:
        # Ukur teks emoji untuk pos tengah obstacle
        bbox = draw.textbbox((0, 0), emoji, font=emoji_font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
    except Exception:
        text_w, text_h = draw.textsize(emoji, font=emoji_font)

    # Posisi emoji agar berada di tengah kotak obstacle
    text_x = x + OBSTACLE_SIZE // 2 - text_w // 2
    text_y = y + OBSTACLE_SIZE // 2 - text_h // 2 - 5

    shadow_color = (0, 0, 0, 150)
    # Gambar bayangan agar emoji lebih kontras
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)]:
        draw.text((text_x + dx, text_y + dy), emoji, font=emoji_font, fill=shadow_color)
    # Gambar emoji putih
    draw.text((text_x, text_y), emoji, font=emoji_font, fill=(255, 255, 255, 255))

    # Update gambar asli OpenCV dengan hasil gambar dari PIL
    img[:] = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

def create_obstacle(frame_width, frame_height, obstacle_id):
    # Membuat obstacle baru secara acak dengan emoji dan gesture yang dipilih acak
    # Posisi mulai di kanan bawah layar
    chosen_type = random.choice(OBSTACLE_TYPES)
    start_x = frame_width - OBSTACLE_SIZE
    start_y = frame_height - OBSTACLE_SIZE - random.randint(50, 150)
    return {
        'id': obstacle_id,
        'x': float(start_x),
        'y': float(start_y),
        'required_gesture': chosen_type['gesture'],  # gesture yang harus dilakukan pemain
        'emoji': chosen_type['emoji'],                # emoji obstacle
        'passed': False                               # apakah obstacle sudah berhasil dilewati
    }

# =========================
# DETEKSI GESTURE TANGAN
# =========================

def detect_gesture(landmarks):
    # Fungsi ini mendeteksi gesture tangan dari posisi landmark yang didapat MediaPipe
    # Mengembalikan nama gesture sesuai yang dikenali

    mp_hands = mp.solutions.hands

    # Landmark ujung jari dan sendi tengah (PIP) untuk semua jari
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

    def is_finger_extended(tip_idx, pip_idx):
        # Jari dianggap terbuka jika posisi ujung jari di atas sendi PIP sedikit (dalam koordinat y)
        return landmarks[tip_idx].y < landmarks[pip_idx].y + 0.02

    def is_finger_bent(tip_idx, pip_idx):
        # Jari dianggap menekuk jika ujung jari lebih rendah dari sendi PIP sedikit
        return landmarks[tip_idx].y > landmarks[pip_idx].y - 0.02

    def is_thumb_open_general():
        # Cek secara kasar apakah ibu jari terbuka
        thumb_x_dist = abs(landmarks[mp_hands.HandLandmark.THUMB_TIP].x - landmarks[mp_hands.HandLandmark.THUMB_MCP].x)
        thumb_y_pos_check = landmarks[mp_hands.HandLandmark.THUMB_TIP].y < landmarks[mp_hands.HandLandmark.THUMB_IP].y + 0.03
        return thumb_x_dist > 0.005 and thumb_y_pos_check

    # Deteksi gesture Pointing 👆: jari telunjuk terbuka, jari lain menekuk, ibu jari dekat telapak
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

    if index_pointing_up and other_fingers_bent and thumb_pointing_pos:
        return "Pointing 👆"

    # Deteksi gesture Peace ✌
    peace_thumb_check = abs(landmarks[mp_hands.HandLandmark.THUMB_TIP].x - landmarks[mp_hands.HandLandmark.THUMB_IP].x) > 0.005
    if (is_finger_extended(finger_tips[1], finger_pips[1]) and
            is_finger_extended(finger_tips[2], finger_pips[2]) and
            is_finger_bent(finger_tips[3], finger_pips[3]) and
            is_finger_bent(finger_tips[4], finger_pips[4]) and
            peace_thumb_check):
        return "Peace ✌"

    # Deteksi gesture Metal 🤘
    if (is_finger_extended(finger_tips[1], finger_pips[1]) and
            is_finger_bent(finger_tips[2], finger_pips[2]) and
            is_finger_bent(finger_tips[3], finger_pips[3]) and
            is_finger_extended(finger_tips[4], finger_pips[4]) and
            is_thumb_open_general()):
        return "Metal 🤘"

    # Deteksi gesture Open Hand 🖐 (semua jari terbuka dan ibu jari juga terbuka)
    if (is_finger_extended(finger_tips[1], finger_pips[1]) and
            is_finger_extended(finger_tips[2], finger_pips[2]) and
            is_finger_extended(finger_tips[3], finger_pips[3]) and
            is_finger_extended(finger_tips[4], finger_pips[4]) and
            is_thumb_open_general()):
        return "Open Hand 🖐"

    # Deteksi gesture Fist ✊ (semua jari menekuk dan ibu jari tertutup)
    all_fingers_bent = (
        is_finger_bent(finger_tips[1], finger_pips[1]) and
        is_finger_bent(finger_tips[2], finger_pips[2]) and
        is_finger_bent(finger_tips[3], finger_pips[3]) and
        is_finger_bent(finger_tips[4], finger_pips[4])
    )
    if all_fingers_bent and not is_thumb_open_general():
        return "Fist ✊"

    # Jika tidak cocok gesture apa pun
    return "Unknown"

# =========================
# PENANGANAN EVENT MOUSE
# =========================

mouse_clicked = False
mouse_x, mouse_y = -1, -1

def mouse_callback(event, x, y, flags, param):
    # Saat klik kiri mouse, simpan posisi klik untuk interaksi tombol
    global mouse_clicked, mouse_x, mouse_y
    if event == cv2.EVENT_LBUTTONDOWN:
        mouse_clicked = True
        mouse_x, mouse_y = x, y

# =========================
# GAMBAR UI & PANEL
# =========================

def draw_detection_zone(img, width, height):
    # Gambar area zona deteksi gesture dengan animasi pulse supaya jelas
    x_start = int(width * DETECTION_ZONE_X_START_RATIO)
    x_end = int(width * DETECTION_ZONE_X_END_RATIO)
    y_start = int(height * DETECTION_ZONE_Y_START_RATIO)
    y_end = int(height * DETECTION_ZONE_Y_END_RATIO)

    pulse_thickness = 4 + int(3 * abs(np.sin(time.time() * 5)))
    pulse_value = int(150 + 105 * abs(np.sin(time.time() * 3)))
    color = (pulse_value, pulse_value, 255)

    overlay = img.copy()
    alpha = 0.2
    cv2.rectangle(overlay, (x_start, y_start), (x_end, y_end), color, -1)
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)
    cv2.rectangle(img, (x_start, y_start), (x_end, y_end), color, pulse_thickness)

    font = cv2.FONT_HERSHEY_SIMPLEX
    text = "Zona Deteksi"
    sz = cv2.getTextSize(text, font, 1, 2)[0]
    tx = x_start + (x_end - x_start - sz[0]) // 2
    ty = y_start + sz[1] + 15
    cv2.putText(img, text, (tx + 3, ty + 3), font, 1, (0, 0, 0), 5)
    cv2.putText(img, text, (tx, ty), font, 1, color, 3)

def draw_hud_panel(img, width, height):
    # Gambar panel HUD atas layar untuk skor dan info lain
    panel_height = 110
    overlay = img.copy()
    cv2.rectangle(overlay, (0, 0), (width, panel_height), (15, 15, 30), -1)
    alpha = 0.7
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)
    cv2.line(img, (0, panel_height), (width, panel_height), (80, 80, 120), 2)

# =========================
# FUNGSI UTAMA GAME LOOP
# =========================

def main():
    # Inisialisasi kamera
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Tidak dapat membuka kamera.")
        return

    # Set ukuran frame kamera
    width, height = 1280, 720
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    # Setup jendela fullscreen dan event klik mouse
    window_name = "Gesture Diagonal Obstacle Game"
    cv2.namedWindow(window_name, cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.setMouseCallback(window_name, mouse_callback)

    # Load suara dan font emoji
    sounds = initialize_pygame_audio()
    emoji_font = load_emoji_font(int(OBSTACLE_SIZE * 0.7))

    # Setup MediaPipe untuk deteksi tangan
    mp_hands_module = mp.solutions.hands
    hands_detector = mp_hands_module.Hands(max_num_hands=1, min_detection_confidence=0.7, min_tracking_confidence=0.7)
    mp_drawing = mp.solutions.drawing_utils
    mp_drawing_styles = mp.solutions.drawing_styles

    # Inisialisasi variabel game
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

    # Posisi tombol di layar menu/game over
    btn_w, btn_h = 240, 70
    btn_start_x = width // 2 - btn_w // 2
    btn_start_y = height // 2 - 120
    btn_instruction_y = height // 2 - 40
    btn_restart_x = btn_start_x
    btn_restart_y = height // 2 + 20
    btn_exit_x = btn_start_x
    btn_exit_y = height // 2 + 110

    # Putar musik latar secara loop
    pygame.mixer.music.play(-1)

    global mouse_clicked, mouse_x, mouse_y

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Gagal membaca frame dari kamera.")
            break

        frame = cv2.flip(frame, 1)  # Mirror agar tangan kanan tetap kanan di kamera
        img = frame.copy()

        # Proses deteksi tangan menggunakan MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        hand_results = hands_detector.process(rgb_frame)

        hand_detected = False
        hand_x, hand_y = -1, -1
        player_gesture = "Unknown"

        if hand_results.multi_hand_landmarks and game_state == STATE_PLAYING:
            for hand_landmarks in hand_results.multi_hand_landmarks:
                # Gambar landmark tangan pada frame
                mp_drawing.draw_landmarks(
                    img, hand_landmarks, mp_hands_module.HAND_CONNECTIONS,
                    mp_drawing_styles.get_default_hand_landmarks_style(),
                    mp_drawing_styles.get_default_hand_connections_style())

                # Dapatkan koordinat pergelangan tangan (wrist)
                hand_x = int(hand_landmarks.landmark[mp_hands_module.HandLandmark.WRIST].x * width)
                hand_y = int(hand_landmarks.landmark[mp_hands_module.HandLandmark.WRIST].y * height)
                hand_detected = True

                # Deteksi gesture berdasarkan landmark tangan
                player_gesture = detect_gesture(hand_landmarks.landmark)

                # Gambar lingkaran pulsa di pergelangan tangan sebagai visual efek
                pulse_radius = 15 + int(5 * abs(np.sin(time.time() * 8)))
                pulse_color_val = int(255 * abs(np.sin(time.time() * 4)))
                cv2.circle(img, (hand_x, hand_y), pulse_radius, (255, pulse_color_val, 255), -1)
                cv2.putText(img, "WRIST", (hand_x + 20, hand_y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 255), 2)

        # ==== Logika game berdasarkan state saat ini ====

        if game_state == STATE_MENU:
            # Tampilkan layar menu utama dengan tombol
            render_menu_screen(img, width, height,
                               btn_start_x, btn_start_y,
                               btn_instruction_y, btn_exit_x, btn_exit_y,
                               btn_w, btn_h)

            # Jika mouse diklik pada tombol menu, tangani aksi tombol
            if mouse_clicked:
                if is_click_on_button(mouse_x, mouse_y, btn_start_x, btn_start_y, btn_w, btn_h):
                    # Mulai permainan baru: reset variabel game
                    (game_state, score, fails, retry_fails, last_failed_obstacle_id,
                     obstacles, obstacle_counter, current_speed_x, current_speed_y,
                     passed_obstacle_ids, in_retry_mode, stalled_obstacle_id,
                     stalled_reason, stalled_obstacle_state) = reset_game(width, height)
                    play_sound(sounds['gameover'])
                elif is_click_on_button(mouse_x, mouse_y, btn_start_x, btn_instruction_y, btn_w, btn_h):
                    game_state = STATE_INSTRUCTIONS
                elif is_click_on_button(mouse_x, mouse_y, btn_exit_x, btn_exit_y, btn_w, btn_h):
                    break  # keluar game
                mouse_clicked = False

        elif game_state == STATE_INSTRUCTIONS:
            # Tampilkan layar instruksi cara main
            render_instructions_screen(img, width, height, btn_start_x, btn_w, btn_h)

            if mouse_clicked:
                if is_click_on_button(mouse_x, mouse_y, btn_start_x, height - 120, btn_w, btn_h):
                    game_state = STATE_MENU  # kembali ke menu utama
                mouse_clicked = False

        elif game_state == STATE_PLAYING:
            # Jalankan logika permainan utama: update obstacle, cek gesture, skor, gagal
            (
                game_state, score, fails, retry_fails, last_failed_obstacle_id,
                in_retry_mode, stalled_obstacle_id, stalled_reason, stalled_obstacle_state,
                obstacles, obstacle_counter, current_speed_x, current_speed_y
            ) = run_gameplay_loop(img, width, height, obstacles, obstacle_counter,
                                  hand_detected, hand_x, hand_y, player_gesture,
                                  score, fails, retry_fails, last_failed_obstacle_id,
                                  in_retry_mode, stalled_obstacle_id, stalled_reason,
                                  stalled_obstacle_state, current_speed_x, current_speed_y,
                                  sounds)

            # Gambar zona deteksi dan panel HUD
            draw_detection_zone(img, width, height)
            draw_hud_panel(img, width, height)

            # Tampilkan info skor, gagal, gesture, dan status retry mode
            render_game_info(img, width, height, score, fails, MAX_FAILS,
                             hand_detected, player_gesture,
                             current_speed_x, current_speed_y, in_retry_mode,
                             obstacles, stalled_obstacle_id, stalled_obstacle_state,
                             sounds)

        elif game_state == STATE_GAMEOVER:
            # Tampilkan layar game over dengan skor akhir dan jokes
            joke_index, joke_timer_start = render_gameover_screen(
                img, width, height, score, JOKES, joke_index, joke_timer_start,
                btn_restart_x, btn_restart_y, btn_exit_x, btn_exit_y, btn_w, btn_h)

            if mouse_clicked:
                if is_click_on_button(mouse_x, mouse_y, btn_restart_x, btn_restart_y, btn_w, btn_h):
                    # Reset game dan mulai ulang musik
                    (game_state, score, fails, retry_fails, last_failed_obstacle_id,
                     obstacles, obstacle_counter, current_speed_x, current_speed_y,
                     passed_obstacle_ids, in_retry_mode, stalled_obstacle_id,
                     stalled_reason, stalled_obstacle_state) = reset_game(width, height)
                    pygame.mixer.music.play(-1)
                    play_sound(sounds['gameover'])
                elif is_click_on_button(mouse_x, mouse_y, btn_exit_x, btn_exit_y, btn_w, btn_h):
                    break  # keluar game
                mouse_clicked = False

        # Tampilkan frame akhir hasil proses di jendela
        cv2.imshow(window_name, img)
        key = cv2.waitKey(10)
        if key == 27:  # ESC tekan untuk keluar
            break

    # Bersihkan sumber daya saat game selesai
    pygame.mixer.music.stop()
    cap.release()
    cv2.destroyAllWindows()


# Penjelasan fungsi render_menu_screen, render_instructions_screen, render_game_info, render_gameover_screen,
# run_gameplay_loop, reset_game ada di kode asli, prinsipnya:
# - render_menu_screen: gambar layar utama dengan tombol mulai, cara main, keluar
# - render_instructions_screen: gambar cara main permainan
# - render_game_info: tampilkan info skor, gesture, kecepatan obstacle dll saat main
# - render_gameover_screen: layar game over dengan skor dan jokes serta tombol mulai ulang dan keluar
# - run_gameplay_loop: fungsi inti update posisi obstacle, cek gesture tangan, update skor, cek gagal, dan mode retry koreksi
# - reset_game: atur ulang variabel game untuk mulai baru


# =========================
# POINT UTAMA PROGRAM
# =========================

if __name__ == "__main__":
    main()  # mulai program dari sini
