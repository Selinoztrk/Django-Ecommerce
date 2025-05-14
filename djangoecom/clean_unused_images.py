import os
import django

# Installing Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'djangoecom.settings')
django.setup()

from django.conf import settings
from store.models import Product

# Files used in the Database
used_files = set()

for product in Product.objects.all():
    if product.image:
        used_files.add(product.image.name)

# All files in the Media folder
media_path = os.path.join(settings.MEDIA_ROOT, 'uploads', 'product')
all_files = set()

for root, dirs, files in os.walk(media_path):
    for file in files:
        rel_path = os.path.relpath(os.path.join(root, file), settings.MEDIA_ROOT)
        all_files.add(rel_path)

# Finding and deleting unused ones
unused_files = all_files - used_files

for file in unused_files:
    file_path = os.path.join(settings.MEDIA_ROOT, file)
    if os.path.exists(file_path):
        os.remove(file_path)
        print(f"Deleted: {file}")
