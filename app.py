import os
import subprocess
import sys
import urllib.request
import zipfile
from PIL import Image, ImageTk
import shutil
import platform
import logging
from tqdm import tqdm
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import time
import json
import webbrowser


# Enhanced GUI style constants
BG_COLOR = "#0d1117"          # Dark background
SURFACE_COLOR = "#161b22"     # Card background
ACCENT_COLOR = "#0BB7E2"      # Accent color
SECONDARY_COLOR = "#21262d"   # Secondary surface
TEXT_COLOR = "#f0f6fc"        # Primary text
MUTED_TEXT = "#8b949e"        # Muted text
DANGER_COLOR = "#da3633"      # Red for stop button
SUCCESS_COLOR = "#2ea043"     # Green for success

# Global variable for process control
current_process = None
stop_requested = False

def download_with_progress(url, output_path):
    response = urllib.request.urlopen(url)
    total = int(response.info().get('Content-Length').strip())
    with open(output_path, 'wb') as f, tqdm(total=total, unit='B', unit_scale=True, desc="Downloading", leave=True, dynamic_ncols=True) as pbar:
        while True:
            if stop_requested:
                f.close()
                os.remove(output_path)
                return False
            chunk = response.read(1024)
            if not chunk:
                break
            f.write(chunk)
            pbar.update(len(chunk))
    return True

def download_realesrgan():
    global stop_requested
    url = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip"
    zip_path = "realesrgan-download.zip"
    extract_path = "realesrgan"

    if not os.path.exists(extract_path):
        print("Downloading Real-ESRGAN version...")
        try:
            if not download_with_progress(url, zip_path):
                return False
            if stop_requested:
                return False
            print("Download completed!")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
            print("Extraction completed!")
            os.remove(zip_path)
        except Exception as e:
            print(f"Download failed: {e}")
            logging.error(f"Download failed: {e}")
            return False
    return True

def enhance_image(input_path, output_path, scale=4):
    global current_process, stop_requested
    
    if platform.system() != "Windows":
        print("❌ Real-ESRGAN only works on Windows. Falling back to OpenCV...")
        return False

    if not download_realesrgan():
        return False

    if stop_requested:
        return False

    exe_path = None
    for root, dirs, files in os.walk("realesrgan"):
        for file in files:
            if file.endswith("realesrgan-ncnn-vulkan.exe"):
                exe_path = os.path.join(root, file)
                break
        if exe_path:
            break

    if not exe_path:
        print("Real-ESRGAN executable not found!")
        return False

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    ext = os.path.splitext(input_path)[1]  # Ambil ekstensi asli (.jpg, .png, dll)
    if not output_path.lower().endswith(ext):
        output_path += ext


    cmd = [exe_path, "-i", input_path, "-o", output_path, "-s", str(scale), "-f", "jpg"]

    try:
        print("Processing image...")
        from subprocess import Popen, PIPE
        start_time = time.time()
        estimated_time = os.path.getsize(input_path) / (1024 * 1024) * 1.5

        with tqdm(total=estimated_time, unit='s', desc=f"Enhancing {os.path.basename(input_path)}", dynamic_ncols=True) as pbar:
            current_process = Popen(cmd, stdout=PIPE, stderr=PIPE, text=True)
            while True:
                if stop_requested:
                    current_process.terminate()
                    return False
                    
                line = current_process.stdout.readline()
                elapsed = time.time() - start_time
                if line:
                    pbar.set_postfix_str(f"{line.strip()} | Elapsed: {elapsed:.1f}s")
                else:
                    pbar.set_postfix_str(f"Elapsed: {elapsed:.1f}s")
                pbar.n = elapsed
                pbar.refresh()
                if current_process.poll() is not None:
                    break
            pbar.n = estimated_time
            pbar.refresh()

        if current_process.returncode == 0 and not stop_requested:
            print("✅ Image enhanced successfully!")
            return True
        else:
            stderr_output = current_process.stderr.read()
            if not stop_requested:
                print(f"❌ Error: {stderr_output}")
                logging.error(stderr_output)
            return False
    except Exception as e:
        print(f"Error running enhancement: {e}")
        logging.error(f"Enhancement error: {e}")
        return False
    finally:
        current_process = None

def enhance_with_opencv(input_path, output_path):
    global stop_requested
    try:
        if stop_requested:
            return False
        import cv2
        print("Using OpenCV for basic upscaling...")
        img = cv2.imread(input_path)
        if img is None:
            print("Could not read input image!")
            return False
        height, width = img.shape[:2]
        new_height, new_width = height * 4, width * 4
        upscaled = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_CUBIC)

        if stop_requested:
            return False

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cv2.imwrite(output_path, upscaled, [cv2.IMWRITE_JPEG_QUALITY, 95])
        with tqdm(total=1, desc=f"OpenCV {os.path.basename(input_path)}", leave=True, dynamic_ncols=True) as pbar:
            pbar.update(1)
        print("✅ Basic upscaling completed!")
        return True
    except ImportError:
        print("OpenCV not installed. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "opencv-python"])
        return enhance_with_opencv(input_path, output_path)
    except Exception as e:
        print(f"OpenCV enhancement failed: {e}")
        logging.error(f"OpenCV error: {e}")
        return False

def show_results(input_path, output_path):
    try:
        with Image.open(input_path) as img:
            orig_size = img.size
            orig_file_size = os.path.getsize(input_path) / (1024 * 1024)
        with Image.open(output_path) as img:
            new_size = img.size
            new_file_size = os.path.getsize(output_path) / (1024 * 1024)
        print(f"\n[+] Results:")
        print(f"   Original: {orig_size[0]}x{orig_size[1]} ({orig_file_size:.1f} MB)")
        print(f"   Enhanced: {new_size[0]}x{new_size[1]} ({new_file_size:.1f} MB)")
        print(f"   Scale factor: {new_size[0]/orig_size[0]:.1f}x")
        print(f"   Output saved as: {output_path}")
    except Exception as e:
        print(f"Could not display results: {e}")
        logging.error(f"Result display error: {e}")

def enhance_folder(input_folder, output_folder, scale=4):
    global stop_requested
    supported_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']
    files = [f for f in os.listdir(input_folder) 
             if os.path.splitext(f)[1].lower() in supported_extensions]
    
    if not files:
        print("No supported image files found in the input folder!")
        return
    
    os.makedirs(output_folder, exist_ok=True)
    
    for file in files:
        if stop_requested:
            break
        input_path = os.path.join(input_folder, file)
        output_path = os.path.join(output_folder, f"enhanced_{file}")
        
        print(f"\nProcessing {file}...")
        if not enhance_image(input_path, output_path, scale):
            if not stop_requested:
                enhance_with_opencv(input_path, output_path)
        if not stop_requested:
            show_results(input_path, output_path)

def create_rounded_button(parent, text, command, bg_color, fg_color="white", width=120, height=35):
    """Create a modern rounded button using Canvas"""
    canvas = tk.Canvas(parent, width=width, height=height, highlightthickness=0, bg=parent.cget('bg'))
    
    # Draw rounded rectangle
    def draw_rounded_rect(x1, y1, x2, y2, radius=10):
        points = []
        for x, y in [(x1, y1 + radius), (x1, y1), (x1 + radius, y1),
                     (x2 - radius, y1), (x2, y1), (x2, y1 + radius),
                     (x2, y2 - radius), (x2, y2), (x2 - radius, y2),
                     (x1 + radius, y2), (x1, y2), (x1, y2 - radius)]:
            points.extend([x, y])
        return canvas.create_polygon(points, smooth=True, fill=bg_color, outline="")
    
    rect = draw_rounded_rect(2, 2, width-2, height-2)
    text_item = canvas.create_text(width//2, height//2, text=text, fill=fg_color, 
                                  font=("Segoe UI", 10, "bold"))
    
    def on_click(event):
        command()
    
    def on_enter(event):
        canvas.itemconfig(rect, fill="#2d333b" if bg_color == SURFACE_COLOR else bg_color)
    
    def on_leave(event):
        canvas.itemconfig(rect, fill=bg_color)
    
    canvas.bind("<Button-1>", on_click)
    canvas.bind("<Enter>", on_enter)
    canvas.bind("<Leave>", on_leave)
    canvas.configure(cursor="hand2")
    
    return canvas

def run_gui():
    global stop_requested
    
    def browse_input():
        path = filedialog.askopenfilename() if not batch_var.get() else filedialog.askdirectory()
        input_entry.delete(0, tk.END)
        input_entry.insert(0, path)

    def browse_output():
        path = filedialog.askdirectory()
        output_entry.delete(0, tk.END)
        output_entry.insert(0, path)

    def stop_process():
        global stop_requested
        stop_requested = True
        if current_process:
            try:
                current_process.terminate()
            except:
                pass
        status_label.config(text="🛑 Process stopped", fg=DANGER_COLOR)
        
    def reset_ui():
        """Reset UI after process completion"""
        start_btn_canvas.pack(pady=5)
        stop_btn_canvas.pack_forget()
        progress_bar.pack_forget()
        progress_bar.stop()

    def show_loading(show=True):
        if show:
            progress_bar.pack(fill=tk.X, padx=20, pady=10)
            progress_bar.start()
            start_btn_canvas.pack_forget()
            stop_btn_canvas.pack(pady=5)
            status_label.config(text="🚀 Processing...\n\nPlease wait while your images are being enhanced.", fg=TEXT_COLOR)
            root.update()
        else:
            reset_ui()

    def see_result():
        output_path = output_entry.get()
        if not output_path:
            messagebox.showwarning("Warning", "Please specify an output folder first")
            return
        
        if batch_var.get():
            if os.path.exists(output_path):
                webbrowser.open(output_path)
            else:
                messagebox.showerror("Error", "Output folder doesn't exist yet")
        else:
            input_path = input_entry.get()
            if not input_path:
                messagebox.showwarning("Warning", "Please specify an input file first")
                return
            
            base_name = os.path.basename(input_path)[0]
            ext = os.path.splitext(input_path)[1]
            enhanced_file = os.path.join(output_path, f"enhanced_{base_name}{ext}")
            
            if not os.path.exists(enhanced_file):
                messagebox.showerror("Error", f"Enhanced file not found:\n{enhanced_file}")
                return
            if os.path.exists(enhanced_file):
                webbrowser.open(enhanced_file)
            else:
                messagebox.showerror("Error", "Enhanced file not found. Please run enhancement first")

    def threaded_start():
        global stop_requested
        stop_requested = False
        
        if not input_entry.get() or not output_entry.get():
            messagebox.showerror("Error", "Please specify input and output paths")
            return
        
        show_loading(True)
        
        def process():
            global stop_requested
            try:
                inp = input_entry.get()
                out = output_entry.get()
                scale = int(scale_var.get())

                if not os.path.exists(inp):
                    messagebox.showerror("Error", "Input path not found")
                    return
                
                os.makedirs(out, exist_ok=True)
                
                if batch_var.get():
                    enhance_folder(inp, out, scale)
                else:
                    output_file = os.path.join(out, f"enhanced_{os.path.basename(inp)}")
                    if not enhance_image(inp, output_file, scale):
                        if not stop_requested:
                            enhance_with_opencv(inp, output_file)
                    if not stop_requested:
                        show_results(inp, output_file)
                
                if not stop_requested:
                    status_label.config(text="✅ Enhancement completed successfully!\n\nYour enhanced images are ready in the output folder.", fg=SUCCESS_COLOR)
                    messagebox.showinfo("Success", "Enhancement completed successfully!")
                else:
                    status_label.config(text="🛑 Process stopped by user\n\nEnhancement was cancelled.", fg=DANGER_COLOR)
                    
            except Exception as e:
                if not stop_requested:
                    messagebox.showerror("Error", f"An error occurred: {str(e)}")
                    status_label.config(text="❌ Enhancement failed\n\nAn error occurred during processing.", fg=DANGER_COLOR)
                logging.error(f"Processing error: {e}")
            finally:
                show_loading(False)
        
        threading.Thread(target=process, daemon=True).start()

    # Create main window with horizontal layout
    root = tk.Tk()
    root.title("AI Image Enhancer")
    root.geometry("1000x600")
    root.configure(bg=BG_COLOR)
    root.resizable(True, True)
    
    # Configure styles
    style = ttk.Style()
    style.theme_use('clam')
    style.configure("TProgressbar", 
                   troughcolor=SECONDARY_COLOR,
                   background=ACCENT_COLOR,
                   borderwidth=1,
                   lightcolor=ACCENT_COLOR,
                   darkcolor=ACCENT_COLOR)
    
    # Main horizontal container
    main_container = tk.Frame(root, bg=BG_COLOR, padx=20, pady=20)
    main_container.pack(expand=True, fill=tk.BOTH)
    
    # Left panel for controls
    left_panel = tk.Frame(main_container, bg=SURFACE_COLOR, width=350)
    left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 10))
    left_panel.pack_propagate(False)
    
    # Right panel for preview/status
    right_panel = tk.Frame(main_container, bg=SURFACE_COLOR)
    right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))
    
    # Title in left panel
    title_label = tk.Label(left_panel, 
                          text="AI Image Enhancer", 
                          font=("Segoe UI", 16, "bold"),
                          bg=SURFACE_COLOR, fg=TEXT_COLOR)
    title_label.pack(pady=(20, 10))
    
    # Subtitle
    subtitle_label = tk.Label(left_panel,
                             text="By Johnstri ",
                             font=("Segoe UI", 9),
                             bg=SURFACE_COLOR, fg=MUTED_TEXT)
    subtitle_label.pack(pady=(0, 20))
    
    # Input section
    input_section = tk.Frame(left_panel, bg=SURFACE_COLOR)
    input_section.pack(fill=tk.X, padx=15, pady=(0, 10))
    
    tk.Label(input_section, text="📁 Input Path", 
             font=("Segoe UI", 10, "bold"), bg=SURFACE_COLOR, fg=TEXT_COLOR).pack(anchor="w", pady=(0, 5))
    
    input_frame = tk.Frame(input_section, bg=SURFACE_COLOR)
    input_frame.pack(fill=tk.X)
    
    input_entry = tk.Entry(input_frame, font=("Segoe UI", 9),
                          bg=SECONDARY_COLOR, fg=TEXT_COLOR, 
                          insertbackground=TEXT_COLOR, bd=0, highlightthickness=1,
                          highlightcolor=ACCENT_COLOR, highlightbackground=SECONDARY_COLOR)
    input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
    
    browse_input_btn = create_rounded_button(input_frame, "Browse", browse_input, ACCENT_COLOR, width=80, height=25)
    browse_input_btn.pack(side=tk.RIGHT)
    
    # Output section
    output_section = tk.Frame(left_panel, bg=SURFACE_COLOR)
    output_section.pack(fill=tk.X, padx=15, pady=(0, 10))
    
    tk.Label(output_section, text="💾 Output Folder", 
             font=("Segoe UI", 10, "bold"), bg=SURFACE_COLOR, fg=TEXT_COLOR).pack(anchor="w", pady=(0, 5))
    
    output_frame = tk.Frame(output_section, bg=SURFACE_COLOR)
    output_frame.pack(fill=tk.X)
    
    output_entry = tk.Entry(output_frame, font=("Segoe UI", 9),
                           bg=SECONDARY_COLOR, fg=TEXT_COLOR,
                           insertbackground=TEXT_COLOR, bd=0, highlightthickness=1,
                           highlightcolor=ACCENT_COLOR, highlightbackground=SECONDARY_COLOR)
    output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
    
    browse_output_btn = create_rounded_button(output_frame, "Browse", browse_output, ACCENT_COLOR, width=80, height=25)
    browse_output_btn.pack(side=tk.RIGHT)
    
    # Settings section
    settings_section = tk.Frame(left_panel, bg=SURFACE_COLOR)
    settings_section.pack(fill=tk.X, padx=15, pady=(0, 15))
    
    tk.Label(settings_section, text="⚙️ Settings", 
             font=("Segoe UI", 10, "bold"), bg=SURFACE_COLOR, fg=TEXT_COLOR).pack(anchor="w", pady=(0, 10))
    
    scale_frame = tk.Frame(settings_section, bg=SURFACE_COLOR)
    scale_frame.pack(fill=tk.X, pady=5)
    
    tk.Label(scale_frame, text="Scale:", font=("Segoe UI", 9),
             bg=SURFACE_COLOR, fg=TEXT_COLOR).pack(side=tk.LEFT)
    
    scale_var = tk.StringVar(value="4")
    scale_2_btn = tk.Radiobutton(scale_frame, text="2x", variable=scale_var, value="2",
                                bg=SURFACE_COLOR, fg=TEXT_COLOR, selectcolor=SECONDARY_COLOR,
                                font=("Segoe UI", 9))
    scale_2_btn.pack(side=tk.LEFT, padx=(10, 5))
    
    scale_4_btn = tk.Radiobutton(scale_frame, text="4x", variable=scale_var, value="4",
                                bg=SURFACE_COLOR, fg=TEXT_COLOR, selectcolor=SECONDARY_COLOR,
                                font=("Segoe UI", 9))
    scale_4_btn.pack(side=tk.LEFT)
    
    batch_var = tk.BooleanVar()
    batch_check = tk.Checkbutton(settings_section, text="Batch Mode [Process Folder]", 
                                variable=batch_var, font=("Segoe UI", 9),
                                bg=SURFACE_COLOR, fg=TEXT_COLOR, selectcolor=SECONDARY_COLOR)
    batch_check.pack(anchor="w", pady=(10, 0))
    
    # Control buttons section
    control_section = tk.Frame(left_panel, bg=SURFACE_COLOR)
    control_section.pack(fill=tk.X, padx=15, pady=15)
    
    start_btn_canvas = create_rounded_button(control_section, "Start Enhancement", 
                                           threaded_start, ACCENT_COLOR, width=200, height=35)
    start_btn_canvas.pack(pady=5)
    
    stop_btn_canvas = create_rounded_button(control_section, "Stop Process", 
                                          stop_process, DANGER_COLOR, width=200, height=35)
    # Initially hidden
    
    see_result_btn = create_rounded_button(control_section, "Show Result", 
                                         see_result, SECONDARY_COLOR, width=200, height=30)
    see_result_btn.pack(pady=(10, 0))
    
    # Progress bar in left panel
    progress_bar = ttk.Progressbar(control_section, mode="indeterminate")
    
    # Right panel content
    right_title = tk.Label(right_panel, text="Status & Preview", 
                          font=("Segoe UI", 14, "bold"),
                          bg=SURFACE_COLOR, fg=TEXT_COLOR)
    right_title.pack(pady=(20, 15))
    
    # Status area
    status_frame = tk.Frame(right_panel, bg=SECONDARY_COLOR, relief=tk.FLAT, bd=0)
    status_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
    
    status_label = tk.Label(status_frame, text="🔄 Ready to enhance images\n\nSelect input file/folder and output directory to begin.", 
                           font=("Segoe UI", 11), bg=SECONDARY_COLOR, fg=TEXT_COLOR, 
                           justify=tk.CENTER, wraplength=300)
    status_label.pack(expand=True)
    
    # Footer
    footer_label = tk.Label(left_panel, 
                           text="Powered by Real-ESRGAN",
                           font=("Segoe UI", 7), bg=SURFACE_COLOR, fg=MUTED_TEXT)
    footer_label.pack(side=tk.BOTTOM, pady=(0, 10))
    
    root.mainloop()

if __name__ == "__main__":
    run_gui()