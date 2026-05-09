import serial
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import sys

# --- AYARLAR ---
SERIAL_PORT = 'COM15'   # Arduino portun
BAUD_RATE = 115200

ZEMIN_REFERANS = 260.0
HEDEF_BEKLENEN = 240.0
TOLERANS = 15.0        

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.5)
    print(f"{SERIAL_PORT} baglandi! Radara geciliyor...")
except Exception as e:
    print(f"Baglanti Hatasi! Detay: {e}")
    sys.exit()

fig, ax = plt.subplots(figsize=(8, 8))
fig.canvas.manager.set_window_title('Otonom Dron - Durum Makinesi (Yer Degistirilmis)')
fig.patch.set_facecolor('#111111') 
ax.set_facecolor('black')

grid_data = np.zeros((3, 3, 3))
im = ax.imshow(grid_data, vmin=0, vmax=1)
ax.set_xticks([])
ax.set_yticks([])

font_koseler = {'ha': 'center', 'va': 'center', 'fontsize': 12, 'fontweight': 'bold'}
font_merkez = {'ha': 'center', 'va': 'center', 'fontsize': 14, 'fontweight': 'bold'}

# --- GÜNCELLENEN KÖŞE KONUMLARI ---
# L5 -> SOL ÜST (x=0, y=0)
txt_L5 = ax.text(0, 0, "SOL ÜST\n(L5) Bekleniyor...", color='white', **font_koseler)

# L1 -> SAĞ ÜST (x=2, y=0)
txt_L1 = ax.text(2, 0, "SAĞ ÜST\n(L1) Bekleniyor...", color='white', **font_koseler)

# L4 -> SOL ALT (x=0, y=2)
txt_L4 = ax.text(0, 2, "SOL ALT\n(L4) Bekleniyor...", color='white', **font_koseler)

# L2 -> SAĞ ALT (x=2, y=2)
txt_L2 = ax.text(2, 2, "SAĞ ALT\n(L2) Bekleniyor...", color='white', **font_koseler)

txt_durum = ax.text(1, 1, "[ DURUM MAKİNESİ ]\nBAŞLATILIYOR", color='cyan', **font_merkez)

# Renkler
C_WHITE  = [1.0, 1.0, 1.0] # Hedef (BEYAZ)
C_RED    = [0.8, 0.1, 0.1] # Sol Üst Zemin
C_GREEN  = [0.1, 0.8, 0.1] # Sağ Üst Zemin
C_BLUE   = [0.2, 0.4, 0.9] # Sol Alt Zemin
C_YELLOW = [0.8, 0.8, 0.1] # Sağ Alt Zemin
C_BLACK  = [0.05, 0.05, 0.05] 

def guncelle(frame):
    try:
        if ser.in_waiting > 0:
            satir = ser.readline().decode('utf-8', errors='ignore').strip()
            
            if satir == "-1,-1,-1,-1":
                txt_durum.set_text("HATA!\nSENSÖR RESETLENİYOR")
                txt_durum.set_color('red')
                return [im, txt_L1, txt_L5, txt_L4, txt_L2, txt_durum]

            if ',' in satir:
                degerler = satir.split(',')
                if len(degerler) == 4:
                    # Gelen Veriler (Sıra Arduino'dan L1, L2, L5, L4 şeklinde geliyor)
                    d_L1 = float(degerler[0]) # Artık SAĞ ÜST
                    d_L2 = float(degerler[1]) # SAĞ ALT
                    d_L5 = float(degerler[2]) # Artık SOL ÜST
                    d_L4 = float(degerler[3]) # SOL ALT
                    
                    h_L1 = abs(d_L1 - HEDEF_BEKLENEN) <= TOLERANS
                    h_L2 = abs(d_L2 - HEDEF_BEKLENEN) <= TOLERANS
                    h_L5 = abs(d_L5 - HEDEF_BEKLENEN) <= TOLERANS
                    h_L4 = abs(d_L4 - HEDEF_BEKLENEN) <= TOLERANS

                    yeni_grid = np.zeros((3, 3, 3))
                    yeni_grid[:, :] = C_BLACK

                    # --- GÜNCELLENEN MATRİS BOYAMALARI ---
                    # SOL ÜST -> Artık L5 (Satır: 0, Sütun: 0)
                    yeni_grid[0, 0] = C_WHITE if h_L5 else C_RED
                    txt_L5.set_text(f"SOL ÜST\n{d_L5:.1f} mm")
                    txt_L5.set_color('black' if h_L5 else 'white')

                    # SAĞ ÜST -> Artık L1 (Satır: 0, Sütun: 2)
                    yeni_grid[0, 2] = C_WHITE if h_L1 else C_GREEN
                    txt_L1.set_text(f"SAĞ ÜST\n{d_L1:.1f} mm")
                    txt_L1.set_color('black' if h_L1 else 'black')

                    # SOL ALT -> L4 (Satır: 2, Sütun: 0)
                    yeni_grid[2, 0] = C_WHITE if h_L4 else C_BLUE
                    txt_L4.set_text(f"SOL ALT\n{d_L4:.1f} mm")
                    txt_L4.set_color('black' if h_L4 else 'white')

                    # SAĞ ALT -> L2 (Satır: 2, Sütun: 2)
                    yeni_grid[2, 2] = C_WHITE if h_L2 else C_YELLOW
                    txt_L2.set_text(f"SAĞ ALT\n{d_L2:.1f} mm")
                    txt_L2.set_color('black' if h_L2 else 'black')

                    # ==========================================
                    # YENİ DURUM MAKİNESİ (KARAR)
                    # ==========================================
                    durum_metni = ""
                    durum_renk = "cyan"
                    
                    if h_L1 and h_L2 and h_L5 and h_L4:
                        durum_metni = "[ KİLİTLENDİ ]\nHedef Tam Merkezde!"
                        durum_renk = "lime"
                        yeni_grid[1, 1] = C_WHITE 
                        
                    elif not h_L1 and not h_L2 and not h_L5 and not h_L4:
                        durum_metni = "[ ARAMA MODU ]\nHedef Bulunamadı"
                        durum_renk = "gray"
                        
                    else:
                        yon_y = ""
                        yon_x = ""
                        
                        # Kural: Hedefi görmeyen (Siyah/Renkli kalan) yöne git.
                        # Üst taraf görmüyorsa (Sol Üst L5 ve Sağ Üst L1) YUKARI git.
                        if (not h_L5 and not h_L1) and (h_L4 or h_L2): yon_y = "YUKARI"
                        # Alt taraf görmüyorsa (Sol Alt L4 ve Sağ Alt L2) AŞAĞI git.
                        elif (not h_L4 and not h_L2) and (h_L5 or h_L1): yon_y = "AŞAĞI"
                        
                        # Sol taraf görmüyorsa (Sol Üst L5 ve Sol Alt L4) SOLA git.
                        if (not h_L5 and not h_L4) and (h_L1 or h_L2): yon_x = "SOLA"
                        # Sağ taraf görmüyorsa (Sağ Üst L1 ve Sağ Alt L2) SAĞA git.
                        elif (not h_L1 and not h_L2) and (h_L5 or h_L4): yon_x = "SAĞA"
                        
                        if yon_y or yon_x:
                            hedef_yon = f"{yon_y} {yon_x}".strip()
                            durum_metni = f"[ DÜZELTME YAPIYOR ]\n--> {hedef_yon} GİT"
                            durum_renk = "yellow"
                        else:
                            durum_metni = "[ KARARSIZLIK ]\nHizalama Bekleniyor"
                            durum_renk = "orange"

                    im.set_data(yeni_grid)
                    txt_durum.set_text(durum_metni)
                    txt_durum.set_color(durum_renk)
                    
    except ValueError: pass 
    except serial.SerialException:
        txt_durum.set_text("BAĞLANTI KOPTU!")
        txt_durum.set_color('red')
    except Exception: pass 
        
    return [im, txt_L1, txt_L5, txt_L4, txt_L2, txt_durum]

ani = animation.FuncAnimation(fig, guncelle, interval=30, blit=True, cache_frame_data=False)

plt.tight_layout()
plt.show()

try: ser.close()
except: pass