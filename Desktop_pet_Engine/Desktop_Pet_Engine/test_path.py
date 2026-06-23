from pathlib import Path
import os

p1 = Path('~/Desktop/test.txt').expanduser()
print(f'Path.expanduser: {p1}')

p2 = os.path.expanduser('~/Desktop/test.txt')
print(f'os.path.expanduser: {p2}')

# Test with the actual desktop image
desktop_img = Path('~/Desktop/img_1782206640_a59bb09a.jpg').expanduser()
print(f'Desktop image: {desktop_img}')
print(f'Exists: {desktop_img.exists()}')
