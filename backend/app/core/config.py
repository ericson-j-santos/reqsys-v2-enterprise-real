from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = 'ReqSys API'
    jwt_secret: str = 'trocar-em-producao'
    jwt_algorithm: str = 'HS256'
    database_url: str = 'sqlite:///./reqsys.db'
    cors_origins: str = 'http://localhost:5173,http://127.0.0.1:5173,http://localhost:8082,http://reqsys.localtest.me:8082'

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(',') if origin.strip()]

settings = Settings()
