import time
import collections
import ctypes
from pynput import mouse, keyboard

keyboard_controller = keyboard.Controller()

# Dinamik Ekran Boyutlarını Al
user32 = ctypes.windll.user32
SCREEN_LEFT = user32.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
SCREEN_TOP = user32.GetSystemMetrics(77)    # SM_YVIRTUALSCREEN
SCREEN_WIDTH = user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
SCREEN_HEIGHT = user32.GetSystemMetrics(79) # SM_CYVIRTUALSCREEN
SCREEN_RIGHT = SCREEN_LEFT + SCREEN_WIDTH - 1

# Ayarlar
REQUIRED_KEY = keyboard.Key.ctrl_l        # Güvenlik Kilidi: Sol CTRL tuşu
TIME_WINDOW = 0.4                         # Saniye cinsinden zaman aralığı
EDGE_TOLERANCE = 5                        # Monitör köşesine değmek için hata payı (piksel)
MIN_DX = 250                              # X Ekseni savurma ivmesi
MIN_DY = 80                               # Y Ekseni (AŞAĞI doğru) çaprazlık eğimi
MAX_Y_LIMIT = SCREEN_TOP + (SCREEN_HEIGHT * 0.6) # Çarpma noktasının üst sınırı
COOLDOWN = 1.0                            # Bekleme süresi

history = collections.deque()
last_trigger_time = 0
is_key_pressed = False

# Klavye Dinleyicisi: Ctrl Tuşunu takip eder
def on_press(key):
    global is_key_pressed
    if key == REQUIRED_KEY:
        is_key_pressed = True

def on_release(key):
    global is_key_pressed
    if key == REQUIRED_KEY:
        is_key_pressed = False
        history.clear() # Tuş bırakılınca hafızayı sıfırla

# Fare Dinleyicisi
def on_move(x, y):
    global last_trigger_time
    
    # EĞER GÜVENLİK TUŞUNA (CTRL) BASILI DEĞİLSE İŞLEM YAPMA
    if not is_key_pressed:
        return

    current_time = time.time()
    history.append((current_time, x, y))
    
    while history and current_time - history[0][0] > TIME_WINDOW:
        history.popleft()
        
    if current_time - last_trigger_time > COOLDOWN:
        
        at_left_edge = (x <= SCREEN_LEFT + EDGE_TOLERANCE)
        if not at_left_edge and (x <= EDGE_TOLERANCE): 
            at_left_edge = True
            
        at_right_edge = (x >= SCREEN_RIGHT - EDGE_TOLERANCE)
        
        if (at_left_edge or at_right_edge) and y < MAX_Y_LIMIT and len(history) >= 2:
            start_time, start_x, start_y = history[0]
            
            dx = x - start_x
            dy = y - start_y
            
            if dy > MIN_DY:  
                if at_left_edge and dx < -MIN_DX:
                    print("<< [CTRL + Sol Eğik Duvar] Önceki Şarkı")
                    keyboard_controller.press(keyboard.Key.media_previous)
                    keyboard_controller.release(keyboard.Key.media_previous)
                    last_trigger_time = current_time
                    history.clear()
                    
                elif at_right_edge and dx > MIN_DX:
                    print(">> [CTRL + Sağ Eğik Duvar] Sonraki Şarkı")
                    keyboard_controller.press(keyboard.Key.media_next)
                    keyboard_controller.release(keyboard.Key.media_next)
                    last_trigger_time = current_time
                    history.clear()

if __name__ == "__main__":
    print("-" * 65)
    print("Mouse Gesture Media Controller (KUSURSUZ GİZLİ EĞİM + CTRL KİLİDİ)")
    print("Hem çapraz kenar kaydırması hem de CTRL tuşu kilidi birleştirildi.")
    print("\nNASIL KULLANILIR:")
    print("1- Sol CTRL tuşuna BASILI TUTUN.")
    print("2- Farenizi sağ veya sol ekran duvarına DOĞRU AŞAĞI ÇAPRAZ EĞİMLİ fırlatın.")
    print("3- Çarptığınız anda şarkı değişir. CTRL tuşu bırakılınca uyku moduna geçer.")
    print("-" * 65)
    
    kbd_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    kbd_listener.start()
    
    try:
        with mouse.Listener(on_move=on_move) as listener:
            listener.join()
    except KeyboardInterrupt:
        print("Program sonlandırıldı.")
