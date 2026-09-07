from pathlib import Path

import nltk

# 使用项目 learn 目录，不受运行脚本时的工作目录影响。
nltk_data_dir = Path(__file__).resolve().parents[2] / 'nltk_data'
nltk_data_dir.mkdir(parents=True, exist_ok=True)
nltk.data.path.insert(0, str(nltk_data_dir))

# 下载分句子模型
nltk.download('punkt', download_dir=str(nltk_data_dir))

# 下载词性标注模型
nltk.download('averaged_perceptron_tagger', download_dir=str(nltk_data_dir))
