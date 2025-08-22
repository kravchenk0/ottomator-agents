#!/bin/bash
set -euo pipefail

echo "🔧 Fixing 504 Gateway Timeout Issues"
echo "===================================="

echo "📋 Current Status:"
echo "  - ALB timeout: 120s -> 600s (10 minutes)"
echo "  - Application timeout: 300s -> 240s (4 minutes)"
echo "  - Added early directory checks"
echo "  - Added better logging"

echo ""
echo "🚀 Deployment Steps:"
echo ""

echo "1. 📦 Copy updated server.py to container:"
echo "   docker cp app/api/server.py lightrag-api:/app/app/api/"

echo ""
echo "2. 🔄 Restart application:"
echo "   docker restart lightrag-api"

echo ""
echo "3. 🏗️  Update ALB timeout via Terraform:"
echo "   cd terraform"
echo "   terraform apply -var-file=\"secrets.tfvars\""

echo ""
echo "4. ⏱️  Wait for ALB update (2-3 minutes)"

echo ""
echo "5. 🧪 Test endpoints:"
echo "   curl -X POST https://api.businessindunes.ai/documents/ingest/scan \\"
echo "     -H \"Authorization: Bearer YOUR_JWT_TOKEN\""

echo ""
echo "📊 Expected improvements:"
echo "  ✅ Faster response for empty/missing directories"
echo "  ✅ Better error handling and logging"
echo "  ✅ Longer ALB timeout for heavy operations"
echo "  ✅ Application timeout safely under ALB limit"

echo ""
echo "⚠️  Important:"
echo "  - Test with small batch first"
echo "  - Monitor logs during operations"
echo "  - Use direct port 8000 for testing if needed"

echo ""
echo "🔗 Direct API access (bypass ALB):"
echo "   curl -X POST http://YOUR_EC2_IP:8000/documents/ingest/scan \\"
echo "     -H \"Authorization: Bearer YOUR_JWT_TOKEN\""

echo ""
echo "Ready to apply fixes? Run the commands above."