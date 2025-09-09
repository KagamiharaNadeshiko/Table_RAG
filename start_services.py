#!/usr/bin/env python3
"""
TableRAG 服务启动脚本
支持启动Flask SQL服务和FastAPI Web服务
包含详细的错误检查和日志功能
"""

import os
import sys
import time
import signal
import subprocess
import threading
import logging
import json
import requests
import socket
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# 配置日志
def setup_logging():
    """设置日志配置"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"startup_{timestamp}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"日志文件: {log_file}")
    return logger

logger = setup_logging()

class ServiceManager:
    """服务管理器"""
    
    def __init__(self):
        self.processes: Dict[str, subprocess.Popen] = {}
        self.running = True
        self.project_root = Path(__file__).parent.absolute()
        
        # 服务配置
        self.services = {
            'flask_sql': {
                'name': 'Flask SQL Service',
                'port': 5000,
                'command': [
                    sys.executable, '-m', 'flask', 'run',
                    '--host', '0.0.0.0',
                    '--port', '5000'
                ],
                'working_dir': self.project_root / 'offline_data_ingestion_and_query_interface' / 'src',
                'env_file': self.project_root / 'offline_data_ingestion_and_query_interface' / 'config' / 'database_config.json',
                'health_url': 'http://localhost:5000/get_tablerag_response',
                'startup_timeout': 30
            },
            'fastapi_web': {
                'name': 'FastAPI Web Service',
                'port': 8000,
                'command': [
                    sys.executable, '-m', 'uvicorn', 'apiserve.main:app',
                    '--host', '0.0.0.0',
                    '--port', '8000',
                    '--reload'
                ],
                'working_dir': self.project_root,
                'env_file': self.project_root / 'apiserve' / 'config' / 'llm_config.json',
                'health_url': 'http://localhost:8000/health',
                'startup_timeout': 30
            }
        }
        
        # 设置信号处理
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """处理中断信号"""
        logger.info(f"接收到信号 {signum}，正在关闭服务...")
        self.running = False
        self.stop_all_services()
        sys.exit(0)
    
    def check_port_available(self, port: int) -> bool:
        """检查端口是否可用"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
                return True
        except OSError:
            return False
    
    def check_dependencies(self) -> bool:
        """检查依赖项"""
        logger.info("检查项目依赖...")
        
        # 检查Python包 - 包名到导入名的映射
        # 分为必需和可选依赖
        required_packages = {
            'flask': 'flask',
            'fastapi': 'fastapi', 
            'uvicorn': 'uvicorn',
            'pandas': 'pandas',
            'sqlalchemy': 'sqlalchemy',
            'pymysql': 'pymysql',
            'requests': 'requests'
        }
        
        optional_packages = {
            'transformers': 'transformers',
            'faiss-cpu': 'faiss'  # faiss-cpu包的导入名是faiss
        }
        
        missing_required = []
        missing_optional = []
        
        # 检查必需依赖
        for package_name, import_name in required_packages.items():
            try:
                __import__(import_name)
                logger.debug(f"✓ {package_name} 已安装")
            except ImportError:
                missing_required.append(package_name)
                logger.debug(f"✗ {package_name} 未安装")
        
        # 检查可选依赖
        for package_name, import_name in optional_packages.items():
            try:
                __import__(import_name)
                logger.debug(f"✓ {package_name} 已安装")
            except ImportError:
                missing_optional.append(package_name)
                logger.debug(f"⚠ {package_name} 未安装 (可选)")
        
        if missing_required:
            logger.error(f"缺少必要的Python包: {', '.join(missing_required)}")
            logger.error("请运行: pip install -r requirements.txt")
            return False
        
        if missing_optional:
            logger.warning(f"缺少可选的Python包: {', '.join(missing_optional)}")
            logger.warning("某些功能可能不可用，但不影响基本服务启动")
        
        logger.info("✓ 所有必需依赖检查通过")
        
        # 检查MySQL连接
        try:
            config_path = self.services['flask_sql']['env_file']
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    db_config = json.load(f)
                
                import pymysql
                conn = pymysql.connect(
                    host=db_config['host'],
                    port=db_config['port'],
                    user=db_config['user'],
                    password=db_config['password'],
                    database=db_config.get('database', 'mysql')
                )
                conn.close()
                logger.info("MySQL连接检查通过")
            else:
                logger.warning(f"数据库配置文件不存在: {config_path}")
        except Exception as e:
            logger.error(f"MySQL连接检查失败: {e}")
            return False
        
        # 检查必要目录
        required_dirs = [
            self.project_root / 'offline_data_ingestion_and_query_interface' / 'src',
            self.project_root / 'apiserve',
            self.project_root / 'online_inference'
        ]
        
        for dir_path in required_dirs:
            if not dir_path.exists():
                logger.error(f"必要目录不存在: {dir_path}")
                return False
        
        logger.info("依赖检查通过")
        return True
    
    def check_config_files(self) -> bool:
        """检查配置文件"""
        logger.info("检查配置文件...")
        
        config_files = [
            self.project_root / 'offline_data_ingestion_and_query_interface' / 'config' / 'database_config.json',
            self.project_root / 'offline_data_ingestion_and_query_interface' / 'config' / 'llm_config.json'
        ]
        
        for config_file in config_files:
            if not config_file.exists():
                logger.error(f"配置文件不存在: {config_file}")
                return False
            
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"配置文件格式错误 {config_file}: {e}")
                return False
        
        logger.info("配置文件检查通过")
        return True
    
    def start_service(self, service_name: str) -> bool:
        """启动单个服务"""
        service_config = self.services[service_name]
        logger.info(f"启动 {service_config['name']}...")
        
        # 检查端口
        if not self.check_port_available(service_config['port']):
            logger.error(f"端口 {service_config['port']} 已被占用")
            return False
        
        try:
            # 设置环境变量
            env = os.environ.copy()
            env['PYTHONPATH'] = str(self.project_root)
            # 指定 Flask 应用入口，避免 "Could not locate a Flask application" 错误
            if service_name == 'flask_sql':
                env['FLASK_APP'] = 'interface:app'
            
            # 启动服务
            process = subprocess.Popen(
                service_config['command'],
                cwd=service_config['working_dir'],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            self.processes[service_name] = process
            
            # 启动日志监控线程
            log_thread = threading.Thread(
                target=self.monitor_service_logs,
                args=(service_name, process),
                daemon=True
            )
            log_thread.start()
            
            # 等待服务启动
            if self.wait_for_service_health(service_name):
                logger.info(f"{service_config['name']} 启动成功")
                return True
            else:
                logger.error(f"{service_config['name']} 启动失败")
                self.stop_service(service_name)
                return False
                
        except Exception as e:
            logger.error(f"启动 {service_config['name']} 时发生错误: {e}")
            return False
    
    def monitor_service_logs(self, service_name: str, process: subprocess.Popen):
        """监控服务日志"""
        service_config = self.services[service_name]
        
        try:
            for line in iter(process.stdout.readline, ''):
                if not self.running:
                    break
                if line.strip():
                    logger.info(f"[{service_config['name']}] {line.strip()}")
        except Exception as e:
            logger.error(f"监控 {service_name} 日志时发生错误: {e}")
    
    def wait_for_service_health(self, service_name: str) -> bool:
        """等待服务健康检查"""
        service_config = self.services[service_name]
        health_url = service_config['health_url']
        timeout = service_config['startup_timeout']
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                if service_name == 'flask_sql':
                    # Flask服务健康检查
                    response = requests.post(
                        health_url,
                        json={'query': 'test', 'table_name_list': []},
                        timeout=5
                    )
                    if response.status_code in [200, 400]:  # 400也是正常的，说明服务在运行
                        return True
                elif service_name == 'fastapi_web':
                    # FastAPI服务健康检查
                    response = requests.get(health_url, timeout=5)
                    if response.status_code == 200:
                        return True
            except requests.exceptions.RequestException:
                pass
            
            time.sleep(1)
        
        return False
    
    def stop_service(self, service_name: str):
        """停止单个服务"""
        if service_name in self.processes:
            process = self.processes[service_name]
            if process.poll() is None:  # 进程仍在运行
                logger.info(f"停止 {self.services[service_name]['name']}...")
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    logger.warning(f"强制终止 {service_name}")
                    process.kill()
                del self.processes[service_name]
    
    def stop_all_services(self):
        """停止所有服务"""
        logger.info("正在停止所有服务...")
        for service_name in list(self.processes.keys()):
            self.stop_service(service_name)
        logger.info("所有服务已停止")
    
    def start_all_services(self) -> bool:
        """启动所有服务"""
        logger.info("开始启动TableRAG服务...")
        
        # 预检查
        if not self.check_dependencies():
            return False
        
        if not self.check_config_files():
            return False
        
        # 启动服务
        success_count = 0
        for service_name in self.services.keys():
            if self.start_service(service_name):
                success_count += 1
            else:
                logger.error(f"服务 {service_name} 启动失败，停止其他服务")
                self.stop_all_services()
                return False
        
        if success_count == len(self.services):
            logger.info("所有服务启动成功！")
            logger.info("服务访问地址:")
            logger.info("  - Web界面: http://localhost:8000")
            logger.info("  - API文档: http://localhost:8000/docs")
            logger.info("  - SQL服务: http://localhost:5000")
            logger.info("按 Ctrl+C 停止所有服务")
            return True
        
        return False
    
    def run(self):
        """运行服务管理器"""
        try:
            if self.start_all_services():
                # 保持运行状态
                while self.running:
                    # 检查服务状态
                    for service_name, process in list(self.processes.items()):
                        if process.poll() is not None:
                            logger.error(f"{self.services[service_name]['name']} 意外停止")
                            self.running = False
                            break
                    time.sleep(1)
            else:
                logger.error("服务启动失败")
                return False
        except KeyboardInterrupt:
            logger.info("用户中断")
        finally:
            self.stop_all_services()
        
        return True

def main():
    """主函数"""
    print("=" * 60)
    print("TableRAG 服务启动脚本")
    print("=" * 60)
    
    # 检查Python版本
    if sys.version_info < (3, 8):
        logger.error("需要Python 3.8或更高版本")
        sys.exit(1)
    
    # 创建服务管理器并运行
    manager = ServiceManager()
    success = manager.run()
    
    if success:
        logger.info("服务正常关闭")
        sys.exit(0)
    else:
        logger.error("服务异常退出")
        sys.exit(1)

if __name__ == "__main__":
    main()
