import subprocess

def mirror_video(input_file, output_file):
    print(f"🔄 Starting mirroring: {input_file}")
    cmd = [
        "ffmpeg", "-y",
        "-i", input_file,
        "-vf", "hflip",
        "-c:a", "copy",
        output_file
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(f"✅ Mirroring finished: {output_file}")
