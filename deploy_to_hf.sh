#!/bin/bash

echo "🚀 Deploying RAG Engine to Hugging Face..."

TARGET_DIR="../hugging-face/rag-engine"

echo "Removing current files" 
rm -rf "$TARGET_DIR/src" "$TARGET_DIR/models" "$TARGET_DIR/services" "$TARGET_DIR/utils" "$TARGET_DIR/repositories" "$TARGET_DIR/api" 
rm -f "$TARGET_DIR/api_client.py" "$TARGET_DIR/requirements.txt" "$TARGET_DIR/config.py" "$TARGET_DIR/main.py" "$TARGET_DIR/gradio_ui.py"

echo "📁 Copying backend"
cp -r src/ "$TARGET_DIR/src"

echo "📄 Copying frontend"
cp gradio_ui.py "$TARGET_DIR/"
cp app.py "$TARGET_DIR/"

echo "📄 Copying requirements.txt..."
cp requirements.txt "$TARGET_DIR/"

echo "✅ Deployment files copied successfully!"
echo "📍 Next steps:"
echo "   cd $TARGET_DIR"
echo "   git add ."
echo "   git commit -m 'Deploy RAG Engine'"
echo "   git push"