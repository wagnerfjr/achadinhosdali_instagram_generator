import os
import random
import time
import shutil
from backend.logger import setup_logger
from backend.utils.script_generator import generate_viral_script, load_config
from backend.utils.text_processor import format_numbers_to_speech
from backend.utils.progress_tracker import update_progress

logger = setup_logger("video_templates")

class VideoTemplateFactory:
    def __init__(self, engine, groq_service, elevenlabs_service):
        self.engine = engine
        self.groq = groq_service
        self.eleven = elevenlabs_service
        self.temp_dir = "temp"
        self.output_dir = "output/videos"

    def _common_pipeline(self, product, include_price: bool):
        """
        Shared logic for script -> audio -> trim -> transcribe -> subtitles.
        """
        product_id = product['id']
        
        # 1. Script Generation
        update_progress(product_id, "scripting", 15, "Gerando roteiro magnético...")
        intro_phrase, script_text = generate_viral_script(product, include_price=include_price)
        
        # 2. Audio Generation (ElevenLabs)
        update_progress(product_id, "audio", 30, "Gerando voz da Li...")
        audio_out = os.path.join(self.temp_dir, f"{product_id}_narration.mp3")
        voice_id = os.getenv("ELEVENLABS_VOICE_ID_LI")
        self.eleven.generate_speech(format_numbers_to_speech(script_text), audio_out, voice_id=voice_id)
        
        if not os.path.exists(audio_out):
            raise RuntimeError("Falha na geração de áudio (ElevenLabs).")

        # 3. Audio Trimming
        update_progress(product_id, "processing", 45, "Removendo silêncio e preparando legendas...")
        trimmed_audio = self.engine.trim_audio_silence(audio_out)
        if os.path.exists(trimmed_audio) and trimmed_audio != audio_out:
            shutil.move(trimmed_audio, audio_out)

        # 4. Transcription & Subtitles (Groq)
        update_progress(product_id, "subtitles", 60, "Sincronizando as legendas karaokê...")
        transcription = self.groq.transcribe_audio(audio_out)
        ass_path = os.path.join(self.temp_dir, f"{product_id}_subs.ass")
        self.groq.convert_to_ass(transcription, ass_path)
        
        return intro_phrase, audio_out, ass_path

    def build_reels(self, product):
        """
        Generates a Reels video: NO Intro Li, NO Price in narration.
        Miolo (Ken Burns/Seller) + CTA Reels.
        """
        product_id = product['id']
        logger.info(f"Building REELS template for {product_id}...")
        
        # 1. Pipeline (No price)
        _, audio_path, ass_path = self._common_pipeline(product, include_price=False)
        
        # 2. Pick CTA Reel
        config = load_config()
        cta_list = config.get("assets", {}).get("cta_reels", [])
        selected_cta = random.choice(cta_list) if cta_list else {"file": "Criação_de_Vídeo_CTA_Instagram.mp4"}
        cta_path = os.path.join("assets/intros", selected_cta['file'])
        
        # 3. Assemble (Intro=None for Reels)
        update_progress(product_id, "assembling", 80, "Montando Reels (Sem preço/Sem Intro)...")
        output_name = f"{product_id}_reel.mp4"
        final_path = self.engine.assemble_hybrid_video(
            product=product,
            intro_video_path=None,  # No Intro for Reels
            audio_path=audio_path,
            ass_path=ass_path,
            music_path=None,
            output_name=output_name,
            outro_video_path=cta_path
        )
        
        return final_path

    def build_stories(self, product):
        """
        Generates a Stories video: Intro Li + Price in narration + CTA Stories.
        """
        product_id = product['id']
        logger.info(f"Building STORIES template for {product_id}...")
        
        # 1. Pipeline (With price)
        intro_phrase, audio_path, ass_path = self._common_pipeline(product, include_price=True)
        
        # 2. Assets (Intro + CTA)
        config = load_config()
        intros = config.get("assets", {}).get("intros", [])
        ctas = config.get("assets", {}).get("cta_stories", [])
        
        # Match intro file to randomized phrase
        intro_file = "Olha_o_que_eu_encontrei_hoje.mp4"
        for intro in intros:
            if intro['phrase'] == intro_phrase:
                intro_file = intro['file']
                break
        
        selected_cta = random.choice(ctas) if ctas else {"file": "Comenta_eu_quero.mp4"}
        
        intro_path = os.path.join("assets/intros", intro_file)
        cta_path = os.path.join("assets/intros", selected_cta['file'])
        
        # 3. Assemble
        update_progress(product_id, "assembling", 80, "Montando Stories (Sanduíche Completo)...")
        output_name = f"{product_id}_story.mp4"
        final_path = self.engine.assemble_hybrid_video(
            product=product,
            intro_video_path=intro_path,
            audio_path=audio_path,
            ass_path=ass_path,
            music_path=None,
            output_name=output_name,
            outro_video_path=cta_path
        )
        
        return final_path
