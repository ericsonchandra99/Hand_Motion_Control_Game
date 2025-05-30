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
# INITIALIZATION SECTION
# =========================

def initialize_pygame_audio():
    """Inisialisasi mixer pygame dan load suara latar dan efek suara secara relatif ke folder resources."""
    pygame.mixer.init()
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    resource_dir = os.path.join(BASE_DIR, "resources")  # pastikan kamu punya folder resources di samping main.py

    try:
        pygame.mixer.music.load(os.path.join(resource_dir, "videoplayback-_1_.wav"))
        sounds = {
            'score': pygame.mixer.Sound(os.path.join(resource_dir, "score.mp3")),
            'warning': pygame.mixer.Sound(os.path.join(resource_dir, "beep-warning-6387.mp3")),
            'gameover': pygame.mixer.Sound(os.path.join(resource_dir, "game-over-arcade-6435.mp3"))
        }
    except Exception as e:
        print(f"Error loading sounds: {e}")
        sounds = {'score': None, 'warning': None, 'gameover': None}

    pygame.mixer.music.set_volume(0.3)
    return sounds

def load_emoji_font(size):
    """
    Memuat font yang mendukung emoji berdasarkan sistem operasi.
    Jika tidak ditemukan, lempar FileNotFoundError.
    """
    system = platform.system()
    
    if system == "Linux":
        path = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"

    elif system == "Windows":
        path = "C:\\Windows\\Fonts\\seguiemj.ttf"

    elif system == "Darwin":  # macOS
        # Cari font emoji alternatif di macOS
        possible_paths = [
            "/System/Library/Fonts/Apple Color Emoji.ttc",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            "/System/Library/Fonts/Supplemental/Apple Symbols.ttf"
        ]
        path = None
        for p in possible_paths:
            if os.path.exists(p):
                path = p
                break
        if path is None:
            raise FileNotFoundError("No suitable emoji font found on macOS.")

    else:
        raise Exception(f"Unsupported operating system: {system}")

    if not os.path.exists(path):
        raise FileNotFoundError(f"Font not found at: {path}")
    
    return ImageFont.truetype(path, size)

# Load emoji font dengan fallback
try:
    emoji_font = load_emoji_font(48)
except Exception as e:
    print(f"Gagal load emoji font: {e}\nMenggunakan default font (emoji bisa tidak muncul).")
    emoji_font = ImageFont.load_default()

# =========================
# CONSTANTS & GLOBALS
# =========================

# Game configuration constants
OBSTACLE_SIZE = 100
INITIAL_OBSTACLE_SPEED_X = 7
INITIAL_OBSTACLE_SPEED_Y = 4
SPEED_INCREASE_FACTOR_X = 0.15
SPEED_INCREASE_FACTOR_Y = 0.075
SCORE_INCREASE_INTERVAL = 5

MAX_FAILS = 3  # Maksimal kegagalan sebelum game over

# Zona deteksi gesture relatif terhadap ukuran frame (rasio)
DETECTION_ZONE_X_START_RATIO = 0.3
DETECTION_ZONE_X_END_RATIO = 0.7
DETECTION_ZONE_Y_START_RATIO = 0.2
DETECTION_ZONE_Y_END_RATIO = 0.8

# Kecepatan obstacle saat mode retry koreksi pose
RETRY_RETREAT_SPEED_X = 5.0
RETRY_RETREAT_SPEED_Y = 3.0
RETRY_ADVANCE_SPEED_X = 5.0
RETRY_ADVANCE_SPEED_Y = 3.0

# Gesture dan Emoji obstacle
OBSTACLE_TYPES = [
    {'gesture': "Open Hand 🖐", 'emoji': "🖐"},
    {'gesture': "Peace ✌", 'emoji': "✌"},
    {'gesture': "Metal 🤘", 'emoji': "🤘"},
    {'gesture': "Fist ✊", 'emoji': "✊"},
    {'gesture': "Pointing 👆", 'emoji': "👆"},
]

# Jokes ditampilkan saat game over bergantian
JOKES = [
    "Kenapa programmer selalu bingung di kamar mandi? Karena gak bisa menemukan bug!",
    "Mengapa komputer suka panas? Karena banyak cache!",
    "Kalau kamu merasa gagal, ingat: 'Segala sesuatu butuh debugging!'",
    "Kenapa keyboard selalu dingin? Karena banyak tombol Ctrl!",
    "Saya tidak malas, saya cuma optimasi waktu."
]

# Game states enumeration
STATE_MENU = 0
STATE_INSTRUCTIONS = 1
STATE_PLAYING = 2
STATE_GAMEOVER = 3

# =========================
# UTILITY FUNCTIONS
# =========================

def play_sound(sound):
    """Mainkan efek suara jika tersedia."""
    if sound:
        sound.play()

def draw_text_with_outline(img, text, pos, font_face, font_scale, text_color, thickness,
                           outline_color=(0, 0, 0), outline_thickness=2):
    """Menggambar teks dengan outline agar terlihat jelas di semua latar."""
    x, y = pos
    offsets = [
        (-outline_thickness, 0), (outline_thickness, 0), (0, -outline_thickness), (0, outline_thickness),
        (-outline_thickness, -outline_thickness), (outline_thickness, outline_thickness),
        (-outline_thickness, outline_thickness), (outline_thickness, -outline_thickness)
    ]
    for dx, dy in offsets:
        cv2.putText(img, text, (x + dx, y + dy), font_face, font_scale, outline_color, thickness)
    cv2.putText(img, text, pos, font_face, font_scale, text_color, thickness)

def draw_button(img, text, x, y, w, h, bg_color, border_color, text_color, font_scale=1):
    """Menggambar tombol persegi panjang dengan teks di tengah."""
    overlay = img.copy()
    cv2.rectangle(overlay, (x, y), (x + w, y + h), bg_color, -1)
    cv2.addWeighted(overlay, 0.9, img, 0.1, 0, img)
    cv2.rectangle(img, (x, y), (x + w, y + h), border_color, 3)

    text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, font_scale, 2)[0]
    text_x = x + (w - text_size[0]) // 2
    text_y = y + (h + text_size[1]) // 2 - 5
    cv2.putText(img, text, (text_x, text_y), cv2.FONT_HERSHEY_DUPLEX, font_scale, text_color, 2)

def is_click_on_button(x, y, btn_x, btn_y, btn_w, btn_h):
    """Cek apakah koordinat (x,y) berada dalam area tombol."""
    return btn_x <= x <= btn_x + btn_w and btn_y <= y <= btn_y + btn_h

def draw_pose_obstacle(img, obs_data, emoji_font):
    """Menggambar emoji obstacle di posisi obstacle."""
    x, y = int(obs_data['x']), int(obs_data['y'])
    emoji = obs_data['emoji']

    pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)

    # Hitung ukuran teks untuk emoji
    try:
        bbox = draw.textbbox((0, 0), emoji, font=emoji_font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
    except Exception:
        text_w, text_h = draw.textsize(emoji, font=emoji_font)

    # Posisi teks agar emoji berada di tengah kotak obstacle
    text_x = x + OBSTACLE_SIZE // 2 - text_w // 2
    text_y = y + OBSTACLE_SIZE // 2 - text_h // 2 - 5

    shadow_color = (0, 0, 0, 150)
    # Gambar bayangan agar emoji kontras
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)]:
        draw.text((text_x + dx, text_y + dy), emoji, font=emoji_font, fill=shadow_color)
    # Gambar emoji
    draw.text((text_x, text_y), emoji, font=emoji_font, fill=(255, 255, 255, 255))

    # Update gambar asli dengan hasil PIL
    img[:] = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

def create_obstacle(frame_width, frame_height, obstacle_id):
    """
    Membuat obstacle baru secara acak dengan posisi awal di sisi kanan bawah layar.
    """
    chosen_type = random.choice(OBSTACLE_TYPES)
    start_x = frame_width - OBSTACLE_SIZE
    start_y = frame_height - OBSTACLE_SIZE - random.randint(50, 150)
    return {
        'id': obstacle_id,
        'x': float(start_x),
        'y': float(start_y),
        'required_gesture': chosen_type['gesture'],
        'emoji': chosen_type['emoji'],
        'passed': False
    }

# =========================
# GESTURE DETECTION LOGIC
# =========================

def detect_gesture(landmarks):
    """
    Deteksi gesture tangan berdasarkan posisi landmark MediaPipe.
    Mengembalikan nama gesture yang dikenali sebagai string.
    """
    mp_hands = mp.solutions.hands

    # Landmark untuk ujung jari dan sendi tengah (PIP)
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
        return landmarks[tip_idx].y < landmarks[pip_idx].y + 0.02

    def is_finger_bent(tip_idx, pip_idx):
        return landmarks[tip_idx].y > landmarks[pip_idx].y - 0.02

    def is_thumb_open_general():
        thumb_x_dist = abs(landmarks[mp_hands.HandLandmark.THUMB_TIP].x - landmarks[mp_hands.HandLandmark.THUMB_MCP].x)
        thumb_y_pos_check = landmarks[mp_hands.HandLandmark.THUMB_TIP].y < landmarks[mp_hands.HandLandmark.THUMB_IP].y + 0.03
        return thumb_x_dist > 0.005 and thumb_y_pos_check

    # Deteksi gesture Pointing 👆
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

    # Deteksi gesture Open Hand 🖐
    if (is_finger_extended(finger_tips[1], finger_pips[1]) and
            is_finger_extended(finger_tips[2], finger_pips[2]) and
            is_finger_extended(finger_tips[3], finger_pips[3]) and
            is_finger_extended(finger_tips[4], finger_pips[4]) and
            is_thumb_open_general()):
        return "Open Hand 🖐"

    # Deteksi gesture Fist ✊
    all_fingers_bent = (
        is_finger_bent(finger_tips[1], finger_pips[1]) and
        is_finger_bent(finger_tips[2], finger_pips[2]) and
        is_finger_bent(finger_tips[3], finger_pips[3]) and
        is_finger_bent(finger_tips[4], finger_pips[4])
    )
    if all_fingers_bent and not is_thumb_open_general():
        return "Fist ✊"

    return "Unknown"

# =========================
# MOUSE EVENT HANDLER
# =========================

mouse_clicked = False
mouse_x, mouse_y = -1, -1

def mouse_callback(event, x, y, flags, param):
    """Callback untuk deteksi klik kiri mouse."""
    global mouse_clicked, mouse_x, mouse_y
    if event == cv2.EVENT_LBUTTONDOWN:
        mouse_clicked = True
        mouse_x, mouse_y = x, y

# =========================
# DRAWING UI PANELS
# =========================

def draw_detection_zone(img, width, height):
    """Gambar zona deteksi gesture dengan efek animasi pulsa."""
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
    """Gambar panel HUD di atas layar untuk menampilkan skor dan info lain."""
    panel_height = 110
    overlay = img.copy()
    cv2.rectangle(overlay, (0, 0), (width, panel_height), (15, 15, 30), -1)
    alpha = 0.7
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)
    cv2.line(img, (0, panel_height), (width, panel_height), (80, 80, 120), 2)

# =========================
# MAIN GAME LOOP
# =========================

def main():
    # Setup kamera
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Tidak dapat membuka kamera.")
        return

    width, height = 1280, 720
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    # Setup window fullscreen dan mouse callback
    window_name = "Gesture Diagonal Obstacle Game"
    cv2.namedWindow(window_name, cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.setMouseCallback(window_name, mouse_callback)

    # Load resources
    sounds = initialize_pygame_audio()
    emoji_font = load_emoji_font(int(OBSTACLE_SIZE * 0.7))

    # MediaPipe Hands setup
    mp_hands_module = mp.solutions.hands
    hands_detector = mp_hands_module.Hands(max_num_hands=1, min_detection_confidence=0.7, min_tracking_confidence=0.7)
    mp_drawing = mp.solutions.drawing_utils
    mp_drawing_styles = mp.solutions.drawing_styles

    # Initialize game variables
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

    # Button positions and sizes
    btn_w, btn_h = 240, 70
    btn_start_x = width // 2 - btn_w // 2
    btn_start_y = height // 2 - 120
    btn_instruction_y = height // 2 - 40
    btn_restart_x = btn_start_x
    btn_restart_y = height // 2 + 20
    btn_exit_x = btn_start_x
    btn_exit_y = height // 2 + 110

    # Play background music loop
    pygame.mixer.music.play(-1)

    global mouse_clicked, mouse_x, mouse_y

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Gagal membaca frame dari kamera.")
            break

        frame = cv2.flip(frame, 1)  # Mirror horizontal
        img = frame.copy()

        # Proses deteksi tangan
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        hand_results = hands_detector.process(rgb_frame)

        hand_detected = False
        hand_x, hand_y = -1, -1
        player_gesture = "Unknown"

        if hand_results.multi_hand_landmarks and game_state == STATE_PLAYING:
            for hand_landmarks in hand_results.multi_hand_landmarks:
                # Gambar landmark tangan
                mp_drawing.draw_landmarks(
                    img, hand_landmarks, mp_hands_module.HAND_CONNECTIONS,
                    mp_drawing_styles.get_default_hand_landmarks_style(),
                    mp_drawing_styles.get_default_hand_connections_style())

                hand_x = int(hand_landmarks.landmark[mp_hands_module.HandLandmark.WRIST].x * width)
                hand_y = int(hand_landmarks.landmark[mp_hands_module.HandLandmark.WRIST].y * height)
                hand_detected = True

                player_gesture = detect_gesture(hand_landmarks.landmark)

                # Visual pulse circle at wrist
                pulse_radius = 15 + int(5 * abs(np.sin(time.time() * 8)))
                pulse_color_val = int(255 * abs(np.sin(time.time() * 4)))
                cv2.circle(img, (hand_x, hand_y), pulse_radius, (255, pulse_color_val, 255), -1)
                cv2.putText(img, "WRIST", (hand_x + 20, hand_y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 255), 2)

        # ==== Game state handling ====
        if game_state == STATE_MENU:
            # Render menu screen
            render_menu_screen(img, width, height,
                               btn_start_x, btn_start_y,
                               btn_instruction_y, btn_exit_x, btn_exit_y,
                               btn_w, btn_h)

            # Handle mouse clicks on menu buttons
            if mouse_clicked:
                if is_click_on_button(mouse_x, mouse_y, btn_start_x, btn_start_y, btn_w, btn_h):
                    # Reset game for new start
                    (game_state, score, fails, retry_fails, last_failed_obstacle_id,
                     obstacles, obstacle_counter, current_speed_x, current_speed_y,
                     passed_obstacle_ids, in_retry_mode, stalled_obstacle_id,
                     stalled_reason, stalled_obstacle_state) = reset_game(width, height)
                    play_sound(sounds['gameover'])
                elif is_click_on_button(mouse_x, mouse_y, btn_start_x, btn_instruction_y, btn_w, btn_h):
                    game_state = STATE_INSTRUCTIONS
                elif is_click_on_button(mouse_x, mouse_y, btn_exit_x, btn_exit_y, btn_w, btn_h):
                    break
                mouse_clicked = False

        elif game_state == STATE_INSTRUCTIONS:
            # Render instruction screen
            render_instructions_screen(img, width, height, btn_start_x, btn_w, btn_h)

            if mouse_clicked:
                if is_click_on_button(mouse_x, mouse_y, btn_start_x, height - 120, btn_w, btn_h):
                    game_state = STATE_MENU
                mouse_clicked = False

        elif game_state == STATE_PLAYING:
            # Jalankan logic game utama (update obstacle, cek gesture, update skor dan gagal)
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

            # Gambar UI (zona deteksi, HUD)
            draw_detection_zone(img, width, height)
            draw_hud_panel(img, width, height)

            # Tampilkan informasi skor, gagal, gesture
            render_game_info(img, width, height, score, fails, MAX_FAILS,
                             hand_detected, player_gesture,
                             current_speed_x, current_speed_y, in_retry_mode,
                             obstacles, stalled_obstacle_id, stalled_obstacle_state,
                             sounds)

        elif game_state == STATE_GAMEOVER:
            # Render game over screen dengan jokes dan tombol
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
                    break
                mouse_clicked = False

        # Tampilkan frame akhir
        cv2.imshow(window_name, img)
        key = cv2.waitKey(10)
        if key == 27:  # ESC
            break

    # Cleanup resources
    pygame.mixer.music.stop()
    cap.release()
    cv2.destroyAllWindows()


# =========================
# RENDERING FUNCTION DEFINITIONS
# =========================

def render_menu_screen(img, w, h, btn_start_x, btn_start_y, btn_instruction_y, btn_exit_x, btn_exit_y, btn_w, btn_h):
    """Render layar menu utama dengan tombol."""
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

    # Tombol
    draw_button(img, "Mulai Game", btn_start_x, btn_start_y, btn_w, btn_h,
                (70, 130, 220), (255, 255, 255), (255, 255, 255), 1.2)
    draw_button(img, "Cara Main", btn_start_x, btn_instruction_y, btn_w, btn_h,
                (120, 180, 90), (255, 255, 255), (255, 255, 255), 1.2)
    draw_button(img, "Keluar", btn_exit_x, btn_exit_y, btn_w, btn_h,
                (220, 70, 70), (255, 255, 255), (255, 255, 255), 1.2)

def render_instructions_screen(img, w, h, btn_start_x, btn_w, btn_h):
    """Render layar instruksi / cara main dengan tombol kembali."""
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

    for i, line in enumerate(instructions):
        draw_text_with_outline(img, line, (50, start_y + i * line_height),
                               cv2.FONT_HERSHEY_SIMPLEX, font_scale_ins, (255, 255, 255), thickness_ins)

    draw_button(img, "Kembali", btn_start_x, h - 120, btn_w, btn_h,
                (70, 130, 220), (255, 255, 255), (255, 255, 255), 1.2)

def render_game_info(img, w, h, score, fails, max_fails, hand_detected, player_gesture,
                     speed_x, speed_y, in_retry_mode, obstacles, stalled_id, stalled_state, sounds):
    """Render skor, status gagal, gesture tangan, dan info lain selama gameplay."""
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
    """Render layar game over dengan tampilan skor dan jokes bergantian."""
    overlay = img.copy()
    cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.75, img, 0.25, 0, img)

    draw_text_with_outline(img, "GAME OVER!", (w // 2 - 180, h // 2 - 120), cv2.FONT_HERSHEY_DUPLEX, 2, (0, 0, 255), 5)
    draw_text_with_outline(img, f"SKOR AKHIR: {score}", (w // 2 - 160, h // 2 - 50), cv2.FONT_HERSHEY_DUPLEX, 1.3, (255, 255, 255), 4)

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

    # Tombol Mulai Ulang dan Keluar
    draw_button(img, "Mulai Ulang", btn_restart_x, btn_restart_y, btn_w, btn_h,
                (70, 130, 220), (255, 255, 255), (255, 255, 255), 1.2)
    draw_button(img, "Keluar", btn_exit_x, btn_exit_y, btn_w, btn_h,
                (220, 70, 70), (255, 255, 255), (255, 255, 255), 1.2)

    return joke_idx, joke_timer

# =========================
# GAMEPLAY CORE FUNCTION
# =========================

def run_gameplay_loop(img, w, h, obstacles, obstacle_counter,
                      hand_detected, hand_x, hand_y, player_gesture,
                      score, fails, retry_fails, last_failed_obstacle_id,
                      in_retry_mode, stalled_obstacle_id, stalled_reason,
                      stalled_obstacle_state, current_speed_x, current_speed_y, sounds):
    """Fungsi utama untuk update posisi obstacle, cek gesture, skor, dan kegagalan."""
    det_zone_x_start = int(w * DETECTION_ZONE_X_START_RATIO)
    det_zone_x_end = int(w * DETECTION_ZONE_X_END_RATIO)
    det_zone_y_start = int(h * DETECTION_ZONE_Y_START_RATIO)
    det_zone_y_end = int(h * DETECTION_ZONE_Y_END_RATIO)

    for obs in obstacles:
        if in_retry_mode and obs['id'] == stalled_obstacle_id:
            # Mode koreksi pose obstacle: mundur dan maju
            if stalled_obstacle_state == 'retreating':
                obs['x'] += RETRY_RETREAT_SPEED_X
                obs['y'] += RETRY_RETREAT_SPEED_Y
                if obs['x'] > det_zone_x_end + OBSTACLE_SIZE / 2:
                    stalled_obstacle_state = 'advancing_for_retry'
                    play_sound(sounds['warning'])
            elif stalled_obstacle_state == 'advancing_for_retry':
                obs['x'] -= RETRY_ADVANCE_SPEED_X
                obs['y'] -= RETRY_ADVANCE_SPEED_Y
                if (det_zone_x_start < obs['x'] + OBSTACLE_SIZE / 2 < det_zone_x_end and
                        det_zone_y_start < obs['y'] + OBSTACLE_SIZE / 2 < det_zone_y_end):
                    stalled_obstacle_state = 'waiting_for_correction'
                    play_sound(sounds['gameover'])
        else:
            # Gerakan obstacle normal (bergerak ke kiri atas)
            obs['x'] -= current_speed_x
            obs['y'] -= current_speed_y

        draw_pose_obstacle(img, obs, load_emoji_font(int(OBSTACLE_SIZE * 0.7)))

        is_in_detection_zone = (det_zone_x_start < obs['x'] + OBSTACLE_SIZE // 2 < det_zone_x_end and
                                det_zone_y_start < obs['y'] + OBSTACLE_SIZE // 2 < det_zone_y_end)

        # Cek obstacle yang sedang di zona dan belum dilewati
        if is_in_detection_zone and not obs['passed']:
            if hand_detected:
                is_hand_in_zone = (det_zone_x_start < hand_x < det_zone_x_end and
                                   det_zone_y_start < hand_y < det_zone_y_end)
                if is_hand_in_zone:
                    # Gesture benar?
                    if player_gesture == obs['required_gesture']:
                        # Sukses koreksi retry mode
                        if in_retry_mode and obs['id'] == stalled_obstacle_id:
                            in_retry_mode = False
                            stalled_obstacle_id = -1
                            stalled_reason = ""
                            stalled_obstacle_state = ''
                            retry_fails = 0
                            last_failed_obstacle_id = None
                            play_sound(sounds['gameover'])
                        if not obs['passed']:
                            obs['passed'] = True
                            score += 1
                            play_sound(sounds['score'])
                            # Tingkatkan kecepatan setiap interval tertentu
                            if score % SCORE_INCREASE_INTERVAL == 0:
                                current_speed_x += SPEED_INCREASE_FACTOR_X
                                current_speed_y += SPEED_INCREASE_FACTOR_Y
                    else:
                        # Gesture salah -> mode retry koreksi
                        if not in_retry_mode:
                            in_retry_mode = True
                            stalled_obstacle_id = obs['id']
                            stalled_reason = "wrong_gesture"
                            stalled_obstacle_state = 'retreating'
                            if last_failed_obstacle_id == stalled_obstacle_id:
                                retry_fails += 1
                            else:
                                retry_fails = 1
                                last_failed_obstacle_id = stalled_obstacle_id
                            fails += 1
                            play_sound(sounds['warning'])
                else:
                    # Tangan tidak di zona -> mode retry koreksi
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
                # Tidak terdeteksi tangan -> mode retry koreksi
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

        # Game over jika gagal melebihi batas
        if fails >= MAX_FAILS or retry_fails >= MAX_FAILS:
            pygame.mixer.music.stop()
            play_sound(sounds['gameover'])
            return STATE_GAMEOVER, score, fails, retry_fails, last_failed_obstacle_id, in_retry_mode, stalled_obstacle_id, stalled_reason, stalled_obstacle_state, obstacles, obstacle_counter, current_speed_x, current_speed_y

        # Retry gagal koreksi jika obstacle keluar dari zona dan dalam status waiting
        if in_retry_mode and obs['id'] == stalled_obstacle_id:
            if ((obs['x'] + OBSTACLE_SIZE // 2 < det_zone_x_start and stalled_obstacle_state == 'waiting_for_correction') or
                (obs['y'] + OBSTACLE_SIZE // 2 < det_zone_y_start and stalled_obstacle_state == 'waiting_for_correction') or
                (obs['x'] > w + OBSTACLE_SIZE)):
                fails += 1
                if fails >= MAX_FAILS:
                    pygame.mixer.music.stop()
                    play_sound(sounds['warning'])
                    return STATE_GAMEOVER, score, fails, retry_fails, last_failed_obstacle_id, in_retry_mode, stalled_obstacle_id, "failed_correction", stalled_obstacle_state, obstacles, obstacle_counter, current_speed_x, current_speed_y
                else:
                    stalled_obstacle_state = 'retreating'
                    play_sound(sounds['warning'])

        # Cek obstacle yang keluar layar tanpa dilewati
        if (obs['x'] + OBSTACLE_SIZE < 0 or obs['y'] < 0) and not obs['passed']:
            if not in_retry_mode:
                fails += 1
                if fails >= MAX_FAILS:
                    pygame.mixer.music.stop()
                    play_sound(sounds['warning'])
                    return STATE_GAMEOVER, score, fails, retry_fails, last_failed_obstacle_id, in_retry_mode, stalled_obstacle_id, "missed_obstacle", stalled_obstacle_state, obstacles, obstacle_counter, current_speed_x, current_speed_y
                else:
                    play_sound(sounds['warning'])

    # Bersihkan obstacle yang sudah keluar layar (kecuali saat game over dan obstacle sedang koreksi)
    obstacles = [obs for obs in obstacles if (obs['x'] + OBSTACLE_SIZE > 0 and obs['y'] + OBSTACLE_SIZE > 0) or
                 (stalled_obstacle_id == obs['id'])]

    # Tambah obstacle baru jika kondisi terpenuhi
    if not in_retry_mode and (len(obstacles) == 0 or
                             (obstacles[-1]['x'] < w - 300 and obstacles[-1]['y'] < h - 300)):
        obstacle_counter += 1
        obstacles.append(create_obstacle(w, h, obstacle_counter))

    return (STATE_PLAYING, score, fails, retry_fails, last_failed_obstacle_id,
            in_retry_mode, stalled_obstacle_id, stalled_reason, stalled_obstacle_state,
            obstacles, obstacle_counter, current_speed_x, current_speed_y)

def reset_game(w, h):
    """Reset semua variabel game untuk memulai permainan baru."""
    return (
        STATE_PLAYING,  # game_state
        0,  # score
        0,  # fails
        0,  # retry_fails
        None,  # last_failed_obstacle_id
        [create_obstacle(w, h, 0)],  # obstacles
        0,  # obstacle_counter
        INITIAL_OBSTACLE_SPEED_X,  # current_speed_x
        INITIAL_OBSTACLE_SPEED_Y,  # current_speed_y
        set(),  # passed_obstacle_ids
        False,  # in_retry_mode
        -1,  # stalled_obstacle_id
        "",  # stalled_reason
        ''  # stalled_obstacle_state
    )

# =========================
# ENTRY POINT
# =========================

if __name__ == "__main__":
    main()
