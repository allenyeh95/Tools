sourse:https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/rate-limits-and-user-limits

fast check: enter in powershell:

curl.exe -X POST https://api.hyperliquid.xyz/info -H "Content-Type: application/json" --data '{\"type\":\"userRateLimit\",\"user\":\"your account address\"}'

