@echo off
setlocal
set "BASE=%~dp0"
if "%KETTLE_HOME%"=="" (
  echo ERRO: defina KETTLE_HOME apontando para o diretorio data-integration.
  exit /b 2
)

if exist "%KETTLE_HOME%\Spoon.bat" (
  rem Instalacao padrao do PDI: usa o launcher oficial Kitchen.bat/Spoon.bat.
  call "%KETTLE_HOME%\kitchen.bat" /file:"%BASE%jobs\jb_treino_criar_dossies.kjb" /level:Basic
  exit /b %ERRORLEVEL%
)

rem Fallback: alguns pacotes de PDI 7.1 vem sem o Spoon.bat original (so com
rem variantes como Spoon-Java8.bat, que por sua vez tambem chama Spoon.bat e
rem falha do mesmo jeito). Nesse caso, chama a engine diretamente via classpath,
rem reproduzindo o que o Kitchen.bat/Spoon.bat fariam por baixo dos panos.
echo AVISO: %KETTLE_HOME%\Spoon.bat nao encontrado; usando invocacao direta da engine.

if not "%PENTAHO_JAVA_HOME%"=="" (
  set "JAVA_BIN=%PENTAHO_JAVA_HOME%\bin\java.exe"
) else (
  set "JAVA_BIN=java"
  echo AVISO: PENTAHO_JAVA_HOME nao definido; usando "java" do PATH. PDI 7.1 requer Java 8 ^(nao roda em Java 9+^).
)

set "CP=%KETTLE_HOME%\classes;%KETTLE_HOME%\.;%KETTLE_HOME%\ui;%KETTLE_HOME%\ui\images;%KETTLE_HOME%\lib\*"

pushd "%KETTLE_HOME%"
"%JAVA_BIN%" -Xms1024m -Xmx2048m "-DKETTLE_HOME=%KETTLE_HOME%" -cp "%CP%" org.pentaho.di.kitchen.Kitchen "/file:%BASE%jobs\jb_treino_criar_dossies.kjb"
set "RC=%ERRORLEVEL%"
popd
exit /b %RC%
