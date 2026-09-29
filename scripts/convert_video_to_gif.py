"""
Utility script to convert MP4 screen recordings to an optimized GIF for README demo showcase.
"""

import os
import sys
import cv2
from PIL import Image

def convert_mp4_to_gif(
    input_video: str,
    output_gif: str = "assets/demo.gif",
    target_width: int = 900,
    fps_divisor: int = 2,
    colors: int = 128
):
    if not os.path.exists(input_video):
        print(f"Error: Video file not found: {input_video}")
        return False

    cap = cv2.VideoCapture(input_video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    target_h = int(orig_h * (target_width / orig_w))
    print(f"Converting '{input_video}' -> '{output_gif}'")
    print(f"Resolution: {orig_w}x{orig_h} -> {target_width}x{target_h} (Every {fps_divisor} frames, {colors} colors)")

    frames = []
    count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if count % fps_divisor == 0:
            resized = cv2.resize(frame, (target_width, target_h), interpolation=cv2.INTER_AREA)
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            im = Image.fromarray(rgb).convert("P", palette=Image.ADAPTIVE, colors=colors)
            frames.append(im)
        count += 1

    cap.release()

    if not frames:
        print("Error: No frames extracted.")
        return False

    os.makedirs(os.path.dirname(os.path.abspath(output_gif)), exist_ok=True)
    duration_ms = int((1000 / fps) * fps_divisor)

    frames[0].save(
        output_gif,
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=0,
        optimize=True
    )

    size_mb = os.path.getsize(output_gif) / (1024 * 1024)
    print(f"Conversion complete! Total frames: {len(frames)}, Output size: {size_mb:.2f} MB")
    return True

if __name__ == "__main__":
    video_input = sys.argv[1] if len(sys.argv) > 1 else "screen_1789874739969.mp4"
    output_path = sys.argv[2] if len(sys.argv) > 2 else "assets/demo.gif"
    convert_mp4_to_gif(video_input, output_path)
