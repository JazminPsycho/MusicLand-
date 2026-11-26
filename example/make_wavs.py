"""Original synthesized tones. No recordings or third party artwork."""
import math,struct,wave
from pathlib import Path
out=Path(__file__).parent
for n,freq in enumerate((220,277.18,329.63),1):
 with wave.open(str(out/f'{n:02d}-Encuentro.wav'),'wb') as w:
  w.setparams((1,2,22050,0,'NONE','not compressed'))
  for sec in range(12):w.writeframes(b''.join(struct.pack('<h',int(4500*math.sin(2*math.pi*freq*(sec+i/22050))*min(1,(sec+i/22050)/.1,(12-sec-i/22050)/.3))) for i in range(22050)))
print('Tres WAV originales de 12 segundos generados.')
