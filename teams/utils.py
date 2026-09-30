import os
from io import BytesIO
from django.core.files.base import ContentFile
from PIL import Image, ImageOps
import logging

logger = logging.getLogger(__name__)

def optimizar_imagen(image_field, max_dimension=1280, quality=80):
    """
    Optimiza y redimensiona una imagen para acelerar la carga del sistema.
    - Corrige orientación EXIF (típica en fotos de teléfonos móviles).
    - Limita la dimensión máxima a max_dimension (1280px).
    - Comprime a JPEG calidad 80 con optimización de tabla de Huffman.
    - Reduce fotos de 5-10MB a 100-250KB manteniendo nitidez perfecta.
    """
    if not image_field or not hasattr(image_field, 'file'):
        return False
    
    try:
        # Abrir imagen con PIL
        image = Image.open(image_field)
        
        # Corregir orientación EXIF
        try:
            image = ImageOps.exif_transpose(image)
        except Exception:
            pass
            
        width, height = image.size
        needs_resize = width > max_dimension or height > max_dimension
        
        if needs_resize:
            image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            
        # Convertir a RGB si tiene canal alfa o paleta
        if image.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            mask = image.split()[3] if len(image.split()) > 3 else None
            background.paste(image, mask=mask)
            image = background
        elif image.mode != 'RGB':
            image = image.convert('RGB')
            
        output = BytesIO()
        image.save(output, format='JPEG', quality=quality, optimize=True)
        output.seek(0)
        
        # Asignar nombre con extensión .jpg
        base_name = os.path.splitext(os.path.basename(image_field.name))[0]
        new_name = f"{base_name}.jpg"
        
        image_field.save(new_name, ContentFile(output.read()), save=False)
        return True
    except Exception as e:
        logger.warning(f"No se pudo optimizar la imagen {getattr(image_field, 'name', '')}: {e}")
        return False
