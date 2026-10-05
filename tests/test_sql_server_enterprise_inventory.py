from pathlib import Path
import importlib.util
P=Path(__file__).resolve().parents[1]/"scripts"/"sql_server_enterprise_inventory.py"
S=importlib.util.spec_from_file_location("sql_inventory",P); M=importlib.util.module_from_spec(S); S.loader.exec_module(M)
def test_query_is_read_only():
 q=M.READ_ONLY_SQL.upper()
 assert not any(x in q for x in ("INSERT ","UPDATE ","DELETE ","MERGE ","DROP ","ALTER ","CREATE ","TRUNCATE ","EXEC "))
 assert "SERVERPROPERTY" in q and "SYS.DATABASES" in q and "QUERY_STORE" in q and "ISJSON" in q
def test_defaults_are_dev_and_no_secret_literal():
 src=P.read_text(encoding="utf-8")
 assert "ReqSysIntegrationDev" in src
 assert "PWD=" not in src and "PASSWORD=" not in src.upper()
 assert "ApplicationIntent=ReadOnly" in src
