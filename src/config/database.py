import os
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from dotenv import load_dotenv

load_dotenv()

class DatabaseManager:
    def __init__(self):
        self.pool = None
        self._initialize_pool()
    
    def _initialize_pool(self):
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        
        self.pool = SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=database_url
        )
    
    def get_connection(self):
        return self.pool.getconn()
    
    def return_connection(self, conn):
        self.pool.putconn(conn)
    
    def execute_query(self, query, params=None):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                if cursor.description:
                    result = cursor.fetchall()
                    conn.commit()  # Commit even for SELECT with RETURNING
                    return result
                else:
                    conn.commit()
                    return None
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            self.return_connection(conn)
    
    def test_connection(self):
        try:
            conn = self.get_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
            self.return_connection(conn)
            print("Database connected successfully")
            return True
        except Exception as error:
            print(f"Database connection failed: {error}")
            return False

# Global database manager instance
db_manager = DatabaseManager()