import customtkinter as ctk
from tkinter import filedialog, messagebox, colorchooser
import tkinter.font as tkfont
import os
from rembg import remove
from PIL import Image, ImageTk, ImageFilter, ImageDraw, ImageFont
import tkinter as tk
import io

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

app = ctk.CTk()
app.title("Thumbnail Generator")
app.geometry("1800x1000")

canvas_width = 1280
canvas_height = 720
canvas = tk.Canvas(app, width=canvas_width, height=canvas_height, bg="black", highlightthickness=0)
canvas.pack(side="left", padx=10, pady=10)

scroll_frame = ctk.CTkScrollableFrame(app, width=500)
scroll_frame.pack(side="right", fill="both", expand=True)

background_path = ""
title1_path = ""
title2_path = ""
person_path = ""
processed_person_path = ""
preview_person_path = ""

bg_img_pil = None
title1_img_pil = None
title2_img_pil = None

text_color = "white"
font_family_var = tk.StringVar(value="Arial")
text_entry = None
all_elements = []
selected_element = None

# Stroke (white border) params for person element
stroke_thickness_var = tk.IntVar(value=30)
stroke_brightness_var = tk.DoubleVar(value=1.0)

# Selection checkboxes dict: element -> (checkbox, variable)
checkboxes = {}

# Helper

def clamp_coords(x, y, w, h):
    margin_x = w * 0.5
    margin_y = h * 0.5
    x = max(-margin_x, min(x, canvas_width - w + margin_x))
    y = max(-margin_y, min(y, canvas_height - h + margin_y))
    return int(x), int(y)

class DraggableElement:
    def __init__(self, canvas, pil_image=None, text=None, x=0, y=0, scale=1.0, rotation=0, color="white", font_size=24, font_family="Arial", is_person=False):
        self.canvas = canvas
        self.scale = scale
        self.rotation = rotation
        self.color = color
        self.font_size = font_size
        self.font_family = font_family
        self.text = text
        self.x, self.y = clamp_coords(x, y, 1, 1)
        self.tk_image = None
        self.canvas_id = None
        self.selected = False
        self.is_person = is_person
        self.stroke_thickness = stroke_thickness_var.get()
        self.stroke_brightness = stroke_brightness_var.get()

        if pil_image:
            self.pil_image_orig = pil_image
        elif text:
            self.pil_image_orig = self.render_text()

        self.update_image()
        self.canvas_id = canvas.create_image(self.x, self.y, image=self.tk_image, anchor="nw")
        self.bind_drag()
        canvas.tag_bind(self.canvas_id, "<Button-1>", lambda e: select_element(self))
        all_elements.append(self)
        add_checkbox_for_element(self)

    def render_text(self):
        font = ImageFont.truetype(self.font_family, int(self.font_size))
        image = Image.new("RGBA", (600, 200), (0,0,0,0))
        draw = ImageDraw.Draw(image)
        draw.text((10, 10), self.text, font=font, fill=self.color)
        return image.rotate(self.rotation, expand=True, resample=Image.BICUBIC, fillcolor=(0,0,0,0))

    def update_image(self):
        img = self.pil_image_orig.resize((int(self.pil_image_orig.width * self.scale), int(self.pil_image_orig.height * self.scale)), Image.Resampling.LANCZOS)
        if self.rotation:
            img = img.rotate(self.rotation, expand=True, resample=Image.BICUBIC)
        if self.is_person:
            img = apply_white_border(img, self.stroke_thickness, self.stroke_brightness)
        self.tk_image = ImageTk.PhotoImage(img)
        if self.canvas_id:
            self.canvas.itemconfig(self.canvas_id, image=self.tk_image)

    def bind_drag(self):
        self.canvas.tag_bind(self.canvas_id, "<ButtonPress-1>", self.on_press)
        self.canvas.tag_bind(self.canvas_id, "<B1-Motion>", self.on_drag)
        self._drag_data = {"x": 0, "y": 0}

    def on_press(self, event):
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y
        select_element(self)

    def on_drag(self, event):
        dx = event.x - self._drag_data["x"]
        dy = event.y - self._drag_data["y"]
        self.canvas.move(self.canvas_id, dx, dy)
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y
        coords = self.canvas.coords(self.canvas_id)
        self.x, self.y = clamp_coords(coords[0], coords[1], self.tk_image.width(), self.tk_image.height())
        self.canvas.coords(self.canvas_id, self.x, self.y)

def apply_white_border(pil_img, border_size, brightness):
    alpha = pil_img.split()[-1]
    # Expand alpha with Gaussian blur for border
    expanded = alpha.filter(ImageFilter.GaussianBlur(radius=border_size))
    # Adjust brightness of border
    expanded = expanded.point(lambda p: min(int(p * brightness), 255))
    border = Image.new("RGBA", pil_img.size, (255, 255, 255, 0))
    white = Image.new("RGBA", pil_img.size, (255, 255, 255, 255))
    border.paste(white, mask=expanded)
    final = Image.alpha_composite(border, pil_img)
    return final

def deselect_element():
    global selected_element
    if selected_element:
        selected_element.selected = False
        cb, var = checkboxes[selected_element]
        var.set(False)
    selected_element = None
    update_controls_for_selection()

def select_element(elem):
    global selected_element
    if selected_element == elem:
        # already selected
        return
    deselect_element()
    selected_element = elem
    selected_element.selected = True
    cb, var = checkboxes[elem]
    var.set(True)
    update_controls_for_selection()

def add_checkbox_for_element(elem):
    var = tk.BooleanVar()
    cb = ctk.CTkCheckBox(scroll_frame, text=f"Select Element {len(checkboxes)+1}", variable=var,
                         command=lambda e=elem, v=var: on_checkbox_change(e, v))
    cb.pack(anchor="w", pady=2)
    checkboxes[elem] = (cb, var)
    update_checkbox_labels()

def on_checkbox_change(elem, var):
    if var.get():
        select_element(elem)
    else:
        if selected_element == elem:
            deselect_element()

def update_checkbox_labels():
    # Update checkbox texts to indicate selection
    for i, elem in enumerate(checkboxes.keys(), 1):
        cb, var = checkboxes[elem]
        label = f"Select Element {i}"
        if elem == selected_element:
            label += " (Selected)"
        cb.configure(text=label)

def update_controls_for_selection():
    if selected_element:
        scale_slider.set(selected_element.scale)
        rotation_slider.set(selected_element.rotation)
        if selected_element.is_person:
            stroke_thickness_slider.configure(state="normal")
            stroke_brightness_slider.configure(state="normal")
            stroke_thickness_var.set(selected_element.stroke_thickness)
            stroke_brightness_var.set(selected_element.stroke_brightness)
        else:
            stroke_thickness_slider.configure(state="disabled")
            stroke_brightness_slider.configure(state="disabled")
    else:
        scale_slider.set(1)
        rotation_slider.set(0)
        stroke_thickness_slider.configure(state="disabled")
        stroke_brightness_slider.configure(state="disabled")
    update_checkbox_labels()
    update_delete_button_state()

def update_selected_scale(value):
    if selected_element:
        selected_element.scale = float(value)
        selected_element.update_image()

def update_selected_rotation(value):
    if selected_element:
        selected_element.rotation = float(value)
        selected_element.update_image()

def update_stroke_thickness(value):
    if selected_element and selected_element.is_person:
        selected_element.stroke_thickness = int(float(value))
        selected_element.update_image()

def update_stroke_brightness(value):
    if selected_element and selected_element.is_person:
        selected_element.stroke_brightness = float(value)
        selected_element.update_image()

def upload_image(label):
    path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png *.jpg *.jpeg")])
    if not path:
        return None
    img = Image.open(path).convert("RGBA")
    label.configure(text=os.path.basename(path))
    return img

def upload_background():
    global bg_img_pil
    bg_img_pil = upload_image(bg_label)
    if bg_img_pil:
        elem = DraggableElement(canvas, pil_image=bg_img_pil, x=0, y=0)
        select_element(elem)

def upload_title1():
    global title1_img_pil
    title1_img_pil = upload_image(title1_label)
    if title1_img_pil:
        elem = DraggableElement(canvas, pil_image=title1_img_pil, x=100, y=100)
        select_element(elem)

def upload_title2():
    global title2_img_pil
    title2_img_pil = upload_image(title2_label)
    if title2_img_pil:
        elem = DraggableElement(canvas, pil_image=title2_img_pil, x=100, y=200)
        select_element(elem)

def upload_person():
    global person_path
    person_path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png *.jpg *.jpeg")])
    if person_path:
        person_label.configure(text=os.path.basename(person_path))
        preview_removal()

def preview_removal():
    global preview_person_path
    if not person_path:
        return
    with open(person_path, "rb") as f:
        data = remove(f.read(), session=None, alpha_matting=True, alpha_matting_foreground_threshold=240, alpha_matting_background_threshold=10, alpha_matting_erode_size=5)
    temp_path = os.path.join(os.path.dirname(__file__), "preview.png")
    with open(temp_path, "wb") as out:
        out.write(data)
    preview_person_path = temp_path
    img = Image.open(temp_path).convert("RGBA")
    # Show preview as a special element
    elem = DraggableElement(canvas, pil_image=img, x=850, y=300, scale=sensitivity_var.get(), is_person=True)
    select_element(elem)

def process_person_image():
    global processed_person_path
    if not person_path:
        messagebox.showwarning("Warning", "No person image uploaded.")
        return
    output_folder = os.path.dirname(person_path)
    border_size = stroke_thickness_var.get()
    brightness = stroke_brightness_var.get()

    # Process with rembg using user settings
    with open(person_path, "rb") as file:
        input_data = file.read()
        output_data = remove(input_data, session=None, alpha_matting=True,
                             alpha_matting_foreground_threshold=240,
                             alpha_matting_background_threshold=10,
                             alpha_matting_erode_size=border_size//2)
    temp_path = os.path.join(output_folder, "person_processed.png")
    with open(temp_path, "wb") as out_file:
        out_file.write(output_data)
    processed_person_path = temp_path
    cutout = Image.open(processed_person_path).convert("RGBA")

    # Add white border around cutout using same border size and brightness
    cutout_with_border = apply_white_border(cutout, border_size, brightness)
    elem = DraggableElement(canvas, pil_image=cutout_with_border, x=850, y=300, is_person=True)
    select_element(elem)
    messagebox.showinfo("Success", "Person image processed and added to canvas.")

def add_text():
    txt = text_entry.get()
    if txt:
        elem = DraggableElement(canvas, text=txt, x=300, y=500, color=text_color, font_family=font_family_var.get())
        select_element(elem)

def pick_text_color():
    global text_color
    _, hex_color = colorchooser.askcolor()
    if hex_color:
        text_color = hex_color

def delete_selected_element():
    global selected_element
    if selected_element:
        # Remove from canvas
        canvas.delete(selected_element.canvas_id)
        # Remove checkbox
        cb, var = checkboxes[selected_element]
        cb.destroy()
        del checkboxes[selected_element]
        # Remove from all_elements
        all_elements.remove(selected_element)
        selected_element = None
        update_controls_for_selection()

def update_delete_button_state():
    if selected_element:
        delete_button.configure(state="normal")
    else:
        delete_button.configure(state="disabled")

def export_canvas():
    # Save canvas as postscript then convert to PNG
    ps = canvas.postscript(colormode='color')
    img = Image.open(io.BytesIO(ps.encode('utf-8')))
    img.save("exported_thumbnail.png")
    messagebox.showinfo("Export", "Saved to exported_thumbnail.png")

# Z-Order Controls
def bring_forward():
    if selected_element:
        canvas.tag_raise(selected_element.canvas_id)

def send_backward():
    if selected_element:
        canvas.tag_lower(selected_element.canvas_id)

# === UI ===
ctk.CTkLabel(scroll_frame, text="Upload Options", font=("Arial", 18)).pack(pady=10)

frame_bg = ctk.CTkFrame(scroll_frame)
frame_bg.pack(pady=5, fill="x")
ctk.CTkButton(frame_bg, text="Upload Background", command=upload_background).pack(side="left", padx=5)
ctk.CTkButton(frame_bg, text="↑", width=30, command=bring_forward).pack(side="left")
ctk.CTkButton(frame_bg, text="↓", width=30, command=send_backward).pack(side="left")
bg_label = ctk.CTkLabel(scroll_frame, text="No file selected")
bg_label.pack()

frame_title1 = ctk.CTkFrame(scroll_frame)
frame_title1.pack(pady=5, fill="x")
ctk.CTkButton(frame_title1, text="Upload Title 1", command=upload_title1).pack(side="left", padx=5)
ctk.CTkButton(frame_title1, text="↑", width=30, command=bring_forward).pack(side="left")
ctk.CTkButton(frame_title1, text="↓", width=30, command=send_backward).pack(side="left")
title1_label = ctk.CTkLabel(scroll_frame, text="No file selected")
title1_label.pack()

frame_title2 = ctk.CTkFrame(scroll_frame)
frame_title2.pack(pady=5, fill="x")
ctk.CTkButton(frame_title2, text="Upload Title 2", command=upload_title2).pack(side="left", padx=5)
ctk.CTkButton(frame_title2, text="↑", width=30, command=bring_forward).pack(side="left")
ctk.CTkButton(frame_title2, text="↓", width=30, command=send_backward).pack(side="left")
title2_label = ctk.CTkLabel(scroll_frame, text="No file selected")
title2_label.pack()

frame_person = ctk.CTkFrame(scroll_frame)
frame_person.pack(pady=5, fill="x")
ctk.CTkButton(frame_person, text="Upload Person", command=upload_person).pack(side="left", padx=5)
ctk.CTkButton(frame_person, text="Process Person Image", command=process_person_image).pack(side="left", padx=5)
ctk.CTkButton(frame_person, text="↑", width=30, command=bring_forward).pack(side="left")
ctk.CTkButton(frame_person, text="↓", width=30, command=send_backward).pack(side="left")
person_label = ctk.CTkLabel(scroll_frame, text="No file selected")
person_label.pack()

ctk.CTkLabel(scroll_frame, text="Add Optional Text", font=("Arial", 16)).pack(pady=10)
text_entry = ctk.CTkEntry(scroll_frame, placeholder_text="Enter text...")
text_entry.pack(pady=5)
ctk.CTkButton(scroll_frame, text="Add Text", command=add_text).pack(pady=5)
ctk.CTkButton(scroll_frame, text="Choose Text Color", command=pick_text_color).pack(pady=5)

font_menu = ctk.CTkOptionMenu(scroll_frame, variable=font_family_var, values=["Arial", "Verdana", "Helvetica", "Times New Roman"])
font_menu.pack(pady=5)

ctk.CTkLabel(scroll_frame, text="Selected Element Transform").pack(pady=10)
scale_slider = ctk.CTkSlider(scroll_frame, from_=0.1, to=3.0, command=update_selected_scale)
scale_slider.pack(pady=5)
rotation_slider = ctk.CTkSlider(scroll_frame, from_=-180, to=180, command=update_selected_rotation)
rotation_slider.pack(pady=5)

ctk.CTkLabel(scroll_frame, text="Person White Border Thickness").pack(pady=(15, 0))
stroke_thickness_slider = ctk.CTkSlider(scroll_frame, from_=1, to=50, variable=stroke_thickness_var, command=update_stroke_thickness)
stroke_thickness_slider.pack(pady=5, fill="x")

ctk.CTkLabel(scroll_frame, text="Person White Border Brightness").pack(pady=(15, 0))
stroke_brightness_slider = ctk.CTkSlider(scroll_frame, from_=0.1, to=2.0, variable=stroke_brightness_var, command=update_stroke_brightness)
stroke_brightness_slider.pack(pady=5, fill="x")

ctk.CTkLabel(scroll_frame, text="Sensitivity Preview Scale").pack(pady=5)
sensitivity_var = tk.DoubleVar(value=1.0)
ctk.CTkSlider(scroll_frame, from_=0.5, to=2.0, variable=sensitivity_var).pack(pady=5)

delete_button = ctk.CTkButton(scroll_frame, text="Delete Selected Element", command=delete_selected_element, state="disabled")
delete_button.pack(pady=10)

ctk.CTkButton(scroll_frame, text="Export Thumbnail", command=export_canvas).pack(pady=10)

update_controls_for_selection()

app.mainloop()
