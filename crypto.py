import aiohttp
import logging
from aiohttp import ClientTimeout

# Импортируем переменные из config
from config import CRYPTO_TOKEN, CHANNEL_URL

logger = logging.getLogger(__name__)

class CryptoPay:
    """Клиент для работы с CryptoPay API"""
    
    def __init__(self):
        self.token = CRYPTO_TOKEN
        self.base_url = "https://pay.crypt.bot/api"
        self.timeout = ClientTimeout(total=15)
    
    def _get_headers(self):
        """Получить заголовки для запроса"""
        return {
            "Crypto-Pay-API-Token": self.token,
            "Content-Type": "application/json"
        }
    
    async def create_invoice(self, amount, currency, description, payload):
        """Создание счета в CryptoPay"""
        url = f"{self.base_url}/createInvoice"
        
        data = {
            "asset": currency,
            "amount": str(amount),
            "description": description,
            "payload": payload,
            "paid_btn_name": "openChannel",
            "paid_btn_url": "https://t.me/helpgrailed",  # Замени на свой канал
            "allow_comments": False,
            "allow_anonymous": False,
            "expires_in": 3600  # 1 час
        }
        
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(url, headers=self._get_headers(), json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get('ok'):
                            logger.info(f"Invoice created for {amount} {currency}")
                            return result['result']
                        else:
                            error_msg = result.get('error', 'Unknown error')
                            logger.error(f"CryptoPay error: {error_msg}")
                            raise Exception(error_msg)
                    else:
                        error_text = await response.text()
                        logger.error(f"HTTP error {response.status}: {error_text}")
                        raise Exception(f"HTTP error: {response.status}")
        except Exception as e:
            logger.error(f"Invoice creation error: {e}")
            raise Exception(f"Failed to create invoice: {str(e)}")
    
    async def get_invoice_status(self, invoice_id):
        """Получить статус счета"""
        url = f"{self.base_url}/getInvoices"
        params = {
            "invoice_ids": invoice_id
        }
        
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url, headers=self._get_headers(), params=params) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get('ok') and result.get('result', {}).get('items'):
                            return result['result']['items'][0]
                    return None
        except Exception as e:
            logger.error(f"Get invoice status error: {e}")
            return None
    
    async def get_balance(self):
        """Получить баланс в CryptoPay"""
        url = f"{self.base_url}/getBalance"
        
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url, headers=self._get_headers()) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get('ok'):
                            return {item['currency_code']: float(item['available']) 
                                   for item in result['result']}
                    return None
        except Exception as e:
            logger.error(f"Get balance error: {e}")
            return None


# Создаем глобальный экземпляр
crypto = CryptoPay()


# Для обратной совместимости с твоим старым кодом
async def create_crypto_invoice(amount, currency, description, payload):
    """Старая функция для совместимости"""
    return await crypto.create_invoice(amount, currency, description, payload)