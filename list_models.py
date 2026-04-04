import google.generativeai as genai
genai.configure(api_key='AIzaSyAf1YQMQU6fy-g-Q8HzhJboeA2g_3j86Lw')
print("사용 가능한 모델:")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(f"  {m.name}")
