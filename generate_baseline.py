import csv
import os
from transformers import pipeline
import pandas as pd

print("Loading model locally (may take a minute on first run)...")
classifier = pipeline("text-classification", model="distilbert-base-uncased-finetuned-sst-2-english")

texts = [
    "I love this product, it's amazing!", "Best purchase ever, highly recommend.",
    "Absolutely wonderful experience", "This is exactly what I needed",
    "Outstanding quality and fast shipping", "Can't ask for better service",
    "Terrible quality, completely disappointed", "Waste of money, don't buy this",
    "Awful experience, would not recommend", "Very poor customer service",
    "Broke after one week of use", "Not worth the price",
]

texts = (texts * 100)[:1000]

os.makedirs('baselines', exist_ok=True)
results = []

print(f"Generating {len(texts)} predictions locally...")
for i, text in enumerate(texts):
    result = classifier(text)[0]
    label = result['label']
    score = result['score']
    pred = 1 if label == 'POSITIVE' else 0
    results.append([pred, score])

    if (i + 1) % 100 == 0:
        print(f"{i+1}/{len(texts)}")

with open('baselines/hf_distilbert_burst_demo_train.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['prediction', 'score'])
    w.writerows(results)

print("\n✅ Baseline dataset created")

df = pd.read_csv('baselines/hf_distilbert_burst_demo_train.csv')
print(df.head())