import asyncio
import random
from datetime import datetime, timedelta
from core.database.models import async_session, ParserCarRequestStatus

async def generate_test_data():
    """Генерирует тестовые данные заявок по месяцам в БД"""
    
    async with async_session() as session:
        try:
            # Генерируем данные на каждый месяц в году
            year = 2024
            request_counter = 1
            
            for month in range(1, 13):
                # Выбираем 3 случайных дня в месяце
                days_in_month = (datetime(year, month + 1, 1) - datetime(year, month, 1)).days if month < 12 else 31
                selected_days = random.sample(range(1, days_in_month + 1), 3)
                
                for day in selected_days:
                    # Создаем 3 успешные заявки
                    for i in range(3):
                        claim_number = f"223200{request_counter:05d}"
                        vin = f"TEST{request_counter:06d}"
                        
                        created_date = datetime(year, month, day).date()
                        started_at = datetime(year, month, day, random.randint(9, 17), random.randint(0, 59))
                        completed_at = started_at + timedelta(minutes=random.randint(5, 30))
                        
                        # Случайный VIN статус для успешных заявок
                        vin_status = random.choice(["VIN", "VIN лайт"])
                        
                        status_record = ParserCarRequestStatus(
                            request_id=claim_number,
                            vin=vin,
                            vin_status=vin_status,
                            comment="ysvg",
                            is_success=True,
                            started_at=started_at,
                            completed_at=completed_at,
                            created_date=created_date
                        )
                        
                        session.add(status_record)
                        request_counter += 1
                    
                    # Создаем 3 неуспешные заявки
                    for i in range(3):
                        claim_number = f"223200{request_counter:05d}"
                        vin = f"TEST{request_counter:06d}"
                        
                        created_date = datetime(year, month, day).date()
                        started_at = datetime(year, month, day, random.randint(9, 17), random.randint(0, 59))
                        completed_at = started_at + timedelta(minutes=random.randint(1, 10))
                        
                        # Для неуспешных заявок используем "Нет"
                        status_record = ParserCarRequestStatus(
                            request_id=claim_number,
                            vin=vin,
                            vin_status="Нет",
                            comment="nsvg",
                            is_success=False,
                            started_at=started_at,
                            completed_at=completed_at,
                            created_date=created_date
                        )
                        
                        session.add(status_record)
                        request_counter += 1
            
            await session.commit()
            print(f"Сгенерировано {request_counter - 1} тестовых заявок в БД")
            print("Данные сохранены в таблицу parser_car_request_status")
            
        except Exception as e:
            await session.rollback()
            print(f"Ошибка при генерации данных: {e}")
            raise

if __name__ == "__main__":
    asyncio.run(generate_test_data()) 