from setuptools import setup, find_packages

setup(
    name="eas-curation",
    version="0.1.0",
    description="Automated image curation pipeline using embedding-based quality scoring",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "torch>=2.0.0,<2.4",
        "transformers>=4.30.0,<5.0",
        "open-clip-torch>=2.0.0",
        "tiktoken>=0.4.0",
        "matplotlib>=3.7.0",
        "Pillow>=9.5.0",
        "numpy<2.0",
        "tqdm>=4.65.0",
        "click>=8.1.0",
        "python-dotenv>=1.0.0",
	"PyYAML>=6.0,<7.0",
        "PySide6>=6.7,<7",
    ],
    entry_points={
        "console_scripts": [
            "eas-curate=eas.eas_curate:main",
        ],
        "gui_scripts": [
            "eas-curation-gui=eas.gui.app:main",
        ],
    },
)
