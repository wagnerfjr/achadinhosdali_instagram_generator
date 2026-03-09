import os
import warnings
# Silence MoviePy/Python 3.12 syntax warnings about escape sequences
warnings.filterwarnings("ignore", category=SyntaxWarning)
import requests
import numpy as np
import subprocess
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont
# Fix for newer Pillow versions that removed ANTIALIAS
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS
try:
    from moviepy import VideoFileClip, VideoClip, AudioFileClip, CompositeAudioClip, CompositeVideoClip, concatenate_videoclips
    import moviepy.video.fx.all as vfx
except ImportError:
    # Extreme fallback for some modular 2.x versions
    from moviepy.video.io.VideoFileClip import VideoFileClip
    from moviepy.video.VideoClip import VideoClip
    from moviepy.audio.io.AudioFileClip import AudioFileClip
    from moviepy.audio.AudioClip import CompositeAudioClip
    from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
    from moviepy.video.compositing.concatenate import concatenate_videoclips
    import moviepy.video.fx.all as vfx
from rembg import remove
from backend.logger import setup_logger
from .utils.text_processor import clean_product_name
from .utils.progress_tracker import update_progress

logger = setup_logger("video_engine_v4")

class VideoEngineV4:
    def __init__(self, output_dir="output/videos", temp_dir="temp"):
        self.output_dir = output_dir
        self.temp_dir = temp_dir
        if not os.path.exists(output_dir): os.makedirs(output_dir)
        if not os.path.exists(temp_dir): os.makedirs(temp_dir)

    def process_product_image(self, img_path, product_id=None, image_url=None):
        """Removes background from product image, downloads if missing."""
        try:
            # Fallback: Download if path is missing
            if not img_path or not os.path.exists(str(img_path)):
                if image_url:
                    logger.info(f"Local image missing, downloading from {image_url}...")
                    img_path = os.path.join(self.temp_dir, f"{product_id}_thumb.jpg")
                    resp = requests.get(image_url)
                    with open(img_path, "wb") as f:
                        f.write(resp.content)
                else:
                    logger.error("No image path and no image URL provided.")
                    return None

            logger.info(f"Removing background for {img_path}...")
            from rembg import remove
            input_image = Image.open(img_path)
            output_image = remove(input_image)
            png_path = str(img_path).replace(".jpg", ".png").replace(".jpeg", ".png")
            output_image.save(png_path)
            return png_path
        except Exception as e:
            logger.error(f"BG removal failed: {e}")
            return img_path

    def _run_ffmpeg(self, cmd, product_id):
        """Safe execution of FFmpeg to avoid pipe deadlocks on Windows."""
        temp_log = os.path.join(self.temp_dir, f"ffmpeg_log_{product_id}.txt")
        with open(temp_log, "w", encoding="utf-8") as log_file:
            try:
                subprocess.run(cmd, check=True, stdout=log_file, stderr=subprocess.STDOUT)
                return True
            except subprocess.CalledProcessError:
                with open(temp_log, "r", encoding="utf-8") as f:
                    err_msg = f.read()
                logger.error(f"FFmpeg error (Product {product_id}): {err_msg}")
                return False

    def trim_audio_silence(self, audio_path, silence_threshold=-50.0, chunk_size=10):
        """Trims leading silence from an audio file using pydub."""
        try:
            from pydub import AudioSegment
            import imageio_ffmpeg
            # Fix WinError 2 by pointing pydub to ffmpeg
            AudioSegment.converter = imageio_ffmpeg.get_ffmpeg_exe()
            
            audio = AudioSegment.from_file(audio_path)
            
            # Detect leading silence
            start_trim = 0
            for i in range(0, len(audio), chunk_size):
                if audio[i:i+chunk_size].dBFS > silence_threshold:
                    start_trim = i
                    break
            
            if start_trim > 0:
                logger.info(f"Trimming {start_trim}ms of leading silence from {audio_path}")
                trimmed_audio = audio[start_trim:]
                trimmed_path = audio_path.replace(".mp3", "_trimmed.mp3")
                trimmed_audio.export(trimmed_path, format="mp3")
                return trimmed_path
            return audio_path
        except Exception as e:
            logger.warning(f"Audio trimming failed: {e}. Using original.")
            return audio_path

    def download_asset(self, url, filename):
        """Downloads an asset from a URL and returns the local path."""
        if not url: return None
        local_path = os.path.join(self.temp_dir, filename)
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            with open(local_path, "wb") as f:
                f.write(resp.content)
            return local_path
        except Exception as e:
            logger.error(f"Download failed for {url}: {e}")
            return None

    def fit_to_vertical(self, clip, bg_color=(30, 30, 30), zoom_fill=False):
        """
        Fits a clip to 1080x1920.
        If zoom_fill is True, it crops/zooms to fill the screen.
        If False, it fits and fills the rest with bg_color.
        """
        W, H = 1080, 1920
        if zoom_fill:
            # Zoom and crop to fill
            return clip.fx(vfx.resize, height=H) if clip.w/clip.h < W/H else clip.fx(vfx.resize, width=W).fx(vfx.crop, x_center=clip.w/2, y_center=clip.h/2, width=W, height=H)
        else:
            # Fit and pad
            return clip.fx(vfx.resize, width=W).set_position(("center", "center"))

    def assemble_hybrid_video(self, product, intro_video_path, audio_path, ass_path, music_path, output_name, outro_video_path=None):
        """
        Assembles a professional Sandwich Video:
        1. Intro (Original Li Audio)
        2. Dynamic Miolo (Seller Video or Photo Carousel)
        3. Outro (CTA Video)
        """
        update_progress(product['id'], "assembling", 80, "Dando o toque profissional: Miolo Dinâmico...")
        
        output_path = os.path.join(self.output_dir, output_name)
        temp_no_sub = os.path.join(self.temp_dir, f"nosub_{output_name}")
        W, H = 1080, 1920
        bg_color_hex = "#1E1E1E" # Cor de fundo Li
        bg_color_rgb = (30, 30, 30)

        # 1. Load Assets & Audios
        def safe_load_clip(path):
            if not path or not os.path.exists(path): return None
            return VideoFileClip(path)

        intro_clip = safe_load_clip(intro_video_path)
        outro_clip = safe_load_clip(outro_video_path)
        
        # Original narration audio (already trimmed in api.py)
        narration_audio = AudioFileClip(audio_path)
        
        # 2. Composition Logic (Structure: Intro + Body + Outro)
        clips = []
        audios = []

        # A. Intro
        intro_duration = 0
        if intro_clip:
            intro_duration = intro_clip.duration
            intro_clip = self.fit_to_vertical(intro_clip, zoom_fill=True)
            audios.append(intro_clip.audio)
            clips.append(intro_clip.without_audio())

        # B. Body (The Product Section)
        body_original_duration = narration_audio.duration
        outro_duration = outro_clip.duration if outro_clip else 0
        
        total_pre_limit = intro_duration + body_original_duration + outro_duration
        MAX_DURATION = 30.0
        
        # If exceeds 30s, we MUST trim the body duration BEFORE any rendering
        if total_pre_limit > MAX_DURATION:
            overage = total_pre_limit - MAX_DURATION
            body_duration = max(1.0, body_original_duration - overage)
            logger.warning(f"Total duration {total_pre_limit}s > {MAX_DURATION}s. Trimming body to {body_duration}s.")
            narration_audio = narration_audio.subclip(0, body_duration)
        else:
            body_duration = body_original_duration

        body_clip = None
        
        # Priority 1: Video from Seller
        seller_video_url = product.get('video_url')
        local_seller_video = self.download_asset(seller_video_url, f"{product['id']}_seller_video.mp4")
        
        if local_seller_video:
            logger.info("Using seller video for dynamic body.")
            s_clip = VideoFileClip(local_seller_video).without_audio()
            # Ensure s_clip has an fps
            if getattr(s_clip, 'fps', None) is None:
                s_clip = s_clip.set_fps(24)
                
            # If seller video is shorter than narration, freeze the last frame
            if s_clip.duration < body_duration:
                # Loop simple workaround for moviepy across versions
                # Just change duration, moviepy natively freezes the last frame if it exceeds
                s_clip = s_clip.set_duration(body_duration)
            else:
                s_clip = s_clip.set_duration(body_duration)
            
            # Blurry background effect or solid color
            # For now, let's use the matching color background
            bg_vid = VideoClip(lambda t: np.full((H, W, 3), bg_color_rgb, dtype='uint8'), duration=body_duration)
            bg_vid.fps = 24
            
            s_clip_resized = s_clip.fx(vfx.resize, width=W).set_position(("center", "center"))
            body_clip = CompositeVideoClip([bg_vid, s_clip_resized]).set_duration(body_duration)
            body_clip.fps = 24
            s_clip.close()
        
        # Priority 2: Photo Carousel
        if not body_clip:
            images_urls = product.get('images', [])
            local_images = []
            for i, url in enumerate(images_urls[:5]): # Up to 5 photos
                png_path = self.process_product_image(None, f"{product['id']}_{i}", url)
                if png_path: local_images.append(png_path)
            
            if local_images:
                logger.info(f"Creating carousel with {len(local_images)} photos.")
                img_clips = []
                per_img_duration = body_duration / len(local_images)
                
                for img_path in local_images:
                    p_img = Image.open(img_path).convert("RGBA")
                    
                    def make_ken_burns_frame(t, img=p_img, p_dur=per_img_duration):
                        # Ken Burns: Zoom in
                        scale = 1.0 + (0.15 * (t / p_dur))
                        target_w = int(W * 0.85 * scale)
                        aspect = img.height / img.width
                        target_h = int(target_w * aspect)
                        
                        resized = img.resize((target_w, target_h), Image.LANCZOS)
                        frame = Image.new('RGB', (W, H), bg_color_rgb)
                        frame.paste(resized, ((W - target_w)//2, (H - target_h)//2), resized)
                        return np.array(frame)
                    
                    v_clip = VideoClip(make_ken_burns_frame, duration=per_img_duration)
                    v_clip.fps = 24
                    img_clips.append(v_clip)
                
                try:
                    from moviepy.video.compositing.concatenate import concatenate_videoclips
                except ImportError:
                    from moviepy.editor import concatenate_videoclips
                    
                body_clip = concatenate_videoclips(img_clips, method="compose")
                body_clip.fps = 24
            else:
                # Fallback: Black screen
                body_clip = VideoClip(lambda t: np.zeros((H, W, 3), dtype='uint8'), duration=body_duration)
                body_clip.fps = 24

        # We don't concatenate using MoviePy to avoid NoneType/FPS bugs
        body_path = os.path.join(self.temp_dir, f"body_{output_name}")
        logger.info(f"Rendering isolated body video to {body_path}...")
        body_clip.write_videofile(body_path, fps=24, codec="libx264", audio=False)
        body_clip.close()

        # Combine audio (trimmed versions already handled above)
        from moviepy.audio.AudioClip import concatenate_audioclips
        master_audio_clips = []
        if intro_clip and intro_clip.audio: master_audio_clips.append(intro_clip.audio)
        master_audio_clips.append(narration_audio)
        if outro_clip and outro_clip.audio: master_audio_clips.append(outro_clip.audio)
        
        master_audio = concatenate_audioclips(master_audio_clips)
        total_duration = master_audio.duration

        # 4. Mix Music
        if music_path and os.path.exists(music_path):
            bg_music = AudioFileClip(music_path).volumex(0.15).set_duration(total_duration)
            final_audio = CompositeAudioClip([master_audio, bg_music])
        else:
            final_audio = master_audio
            
        audio_path_combined = os.path.join(self.temp_dir, f"audio_{output_name}.mp3")
        final_audio.write_audiofile(audio_path_combined, fps=44100)
        
        # Cleanup clips & audio
        if intro_clip: intro_clip.close()
        if outro_clip: outro_clip.close()
        master_audio.close()
        if 'bg_music' in locals(): bg_music.close()

        import time
        time.sleep(1)

        # 5. FFmpeg composition: [intro, body, outro] + Audio + Subtitles
        logger.info("Using FFmpeg to concatenate sandwich components...")
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        safe_ass_path = ass_path.replace("\\", "/").replace(":", "\\:")
        
        inputs = []
        filter_complex = ""
        v_idx = 0
        
        # Force same sizing for all to avoid compose errors
        if intro_video_path and os.path.exists(intro_video_path):
            inputs.extend(["-i", intro_video_path])
            filter_complex += f"[{v_idx}:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=24,format=yuv420p[v{v_idx}];"
            v_idx += 1
            
        inputs.extend(["-i", body_path])
        filter_complex += f"[{v_idx}:v]scale=1080:1920,setsar=1,fps=24,format=yuv420p,ass='{safe_ass_path}'[v{v_idx}];"
        v_idx += 1
        
        if outro_video_path and os.path.exists(outro_video_path):
            inputs.extend(["-i", outro_video_path])
            filter_complex += f"[{v_idx}:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=24,format=yuv420p[v{v_idx}];"
            v_idx += 1

        # Add the combined audio
        inputs.extend(["-i", audio_path_combined])
        a_idx = v_idx # the mixed audio is the last input
        
        concat_str = ""
        for i in range(v_idx): concat_str += f"[v{i}]"
        filter_complex += f"{concat_str}concat=n={v_idx}:v=1:a=0[outv]"
        
        cmd = [
            ffmpeg_exe, *inputs,
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-map", f"{a_idx}:a",
            "-c:v", "libx264", "-crf", "22", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", "-y", output_path
        ]
        
        try:
            logger.info(f"Running FFmpeg: {' '.join(cmd)}")
            success = self._run_ffmpeg(cmd, product['id'])
            if not success:
                raise Exception("Falha na composição sandwich via FFmpeg. Verifique os logs.")
            logger.info(f"Sandwich video created: {output_path}")
        except Exception as e:
            logger.error(f"FFmpeg sandwich fail: {e}")
            raise e
            
        update_progress(product['id'], "completed", 100, "Vídeo Pro gerado com sucesso via FFmpeg!")
        return output_path

    def assemble_final_video(self, product, did_video_path, audio_path, ass_path, music_path, output_name):
        """
        Assembles the final video with all components.
        - did_video_path: The lip-sync video from D-ID.
        - product: dict with price, discount, etc.
        - ass_path: Path to .ASS subtitles.
        - music_path: Background music path.
        """
        update_progress(product['id'], "assembling", 80, "Iniciando montagem final do vídeo...")
        
        output_path = os.path.join(self.output_dir, output_name)
        
        # 1. Load Background Video (Li talking)
        clip = VideoFileClip(did_video_path)
        W, H = clip.size # Usually 1080x1920 if D-ID supports or we resize
        
        # 2. Process Product Overlay
        prod_raw = product.get('local_image_path')
        prod_url = product.get('image_url')
        prod_png = self.process_product_image(prod_raw, product.get('id'), prod_url)
        
        if not prod_png or not os.path.exists(prod_png):
            logger.warning("Continuing without product overlay (image missing)")
            final_clip = clip
        else:
            prod_img = Image.open(prod_png).convert("RGBA")
            # Create Product Overlay Clip
            # Position: Bottom Right or Side
            def make_overlay_frame(t):
                # Dynamic entrance for product
                scale = max(0.01, t) if t < 1 else 1.0

                pw = int(W * 0.5 * scale)
                # Ensure at least 1px
                pw = max(1, pw)
                
                aspect = prod_img.height / prod_img.width
                ph = int(pw * aspect)
                ph = max(1, ph)

                resized = prod_img.resize((pw, ph), Image.LANCZOS)

                # Create transparent layer
                overlay = Image.new('RGBA', (W, H), (0,0,0,0))
                overlay.paste(resized, (W - pw - 50, H - ph - 300), resized)
                return np.array(overlay)

            overlay_clip = VideoClip(make_overlay_frame, duration=clip.duration)
            final_clip = CompositeVideoClip([clip, overlay_clip])
        
        # 5. Add Music
        if music_path and os.path.exists(music_path):
            bg_music = AudioFileClip(music_path).volumex(0.3).set_duration(clip.duration)
            original_audio = AudioFileClip(audio_path)
            mixed_audio = CompositeAudioClip([original_audio, bg_music])
            final_clip = final_clip.set_audio(mixed_audio)
        else:
            final_clip = final_clip.set_audio(AudioFileClip(audio_path))

        # 6. Burn Subtitles (FFmpeg filter)
        # We'll use temporary file for no-subtitle render, then ffmpeg for subs
        temp_no_sub = os.path.join(self.temp_dir, f"nosub_{output_name}")
        
        logger.info(f"Rendering intermediate video to {temp_no_sub}...")
        final_clip.write_videofile(temp_no_sub, fps=24, codec="libx264", audio_codec="aac", pixel_format="yuv420p")
        
        # Burn subs via subprocess ffmpeg for better control over .ASS
        logger.info(f"Burning subtitles from {ass_path}...")
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        
        # We need to escape the path for the 'ass' filter in FFmpeg on Windows
        # Escaping backslashes for FFmpeg VF filter: \ -> \\ and : -> \:
        safe_ass_path = ass_path.replace("\\", "/").replace(":", "\\:")
        
        cmd = [
            ffmpeg_exe,
            "-i", temp_no_sub,
            "-vf", f"format=yuv420p,ass='{safe_ass_path}'",
            "-c:v", "libx264",
            "-crf", "23",
            "-c:a", "copy",
            "-movflags", "+faststart",
            "-y",
            output_path
        ]
        
        try:
            success = self._run_ffmpeg(cmd, product['id'])
            if not success:
                raise Exception("FFmpeg burning failed")
            logger.info(f"Final video with subtitles created at {output_path}")
        except Exception:
            # If sub burn fails, at least provide the no-sub version as fallback
            import shutil
            shutil.copy(temp_no_sub, output_path)
            logger.warning(f"Using video without subtitles as fallback at {output_path}")
        finally:
            try:
                final_clip.close()
                clip.close()
                if 'overlay_clip' in locals():
                    overlay_clip.close()
                if 'mixed_audio' in locals():
                    mixed_audio.close()
                elif 'original_audio' in locals():
                    original_audio.close()
            except Exception as e:
                logger.warning(f"Error closing clips in assemble_final_video: {e}")
        
        update_progress(product['id'], "completed", 100, "Vídeo gerado com sucesso!")
        return output_path
