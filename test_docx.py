import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import create_word_document

print("Testing create_word_document...")
create_word_document("La Inteligencia Artificial")
print("Done.")
