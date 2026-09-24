import sys, types, time, numpy as np, torch
torch.set_num_threads(2)
src = open('psu2_pythia_colab_v2.py').read()
src = src.replace("subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'transformers', 'datasets', 'scikit-learn'])", "")
src = src.replace("STEPS = [0, 512, 1000, 2000, 4000, 8000, 16000, 32000, 64000, 143000]", "STEPS = [0, 143000]")
src = src.replace("L, NSEQ, LAYER, KCLS, W = 256, 600, -2, 16, 8", "L, NSEQ, LAYER, KCLS, W = 256, 32, -2, 16, 8")
src = src.replace("OUT = 'psu2_pythia_rows.json'", "OUT = '/tmp/test_rows.json'")
fake_ds = types.ModuleType('datasets')
fake_ds.load_dataset = lambda name, split: {'text': ['x'] * 200}
sys.modules['datasets'] = fake_ds
import transformers
from transformers import GPTNeoXConfig, GPTNeoXForCausalLM, AutoTokenizer
class FakeTok:
    def __init__(self): self.rng = np.random.default_rng(0)
    def __call__(self, t): return {'input_ids': self.rng.integers(0, 50277, 300).tolist()}
    def __len__(self): return 50277
AutoTokenizer.from_pretrained = staticmethod(lambda name: FakeTok())
cfg = GPTNeoXConfig(vocab_size=50304, hidden_size=512, num_hidden_layers=6, num_attention_heads=8,
                    intermediate_size=2048, rotary_pct=0.25, max_position_embeddings=2048, use_parallel_residual=True)
Orig = GPTNeoXForCausalLM
def fake_fp(name, revision=None):
    torch.manual_seed(abs(hash(revision)) % 1000)
    return Orig(cfg)
GPTNeoXForCausalLM.from_pretrained = staticmethod(fake_fp)
import os
if os.path.exists('/tmp/test_rows.json'): os.remove('/tmp/test_rows.json')
t = time.time()
exec(compile(src, 'v2', 'exec'), {'__name__': '__main__'})
print('TEST TIME', round(time.time() - t, 1))
