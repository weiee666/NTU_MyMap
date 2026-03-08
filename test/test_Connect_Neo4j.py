import socket
from neo4j import GraphDatabase, exceptions

# 配置Neo4j连接信息
NEO4J_BOLT_URL = "neo4j+s://08b3a13d.databases.neo4j.io"
NEO4J_USER = "08b3a13d"  # 替换成你的Neo4j用户名（默认是neo4j）
NEO4J_PASSWORD = "gHL50wO4b5ecu8tA8xv2tH_8ghfdMlELGtMdt8e5cvQ"  # 替换成你的Neo4j密码

def test_port_connectivity(host, port):
    """第一步：检测端口是否可达（基础网络连通性）"""
    print(f"=== 第一步：检测 {host}:{port} 端口连通性 ===")
    try:
        # 创建TCP套接字，超时时间5秒
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        if result == 0:
            print(f"✅ 端口 {host}:{port} 可达（网络层面连通）")
            return True
        else:
            print(f"❌ 端口 {host}:{port} 不可达（可能是防火墙/安全组拦截，或Neo4j未启动）")
            return False
    except Exception as e:
        print(f"❌ 端口检测失败：{str(e)}")
        return False
    finally:
        sock.close()

def test_neo4j_bolt_connection(bolt_url, user, password):
    """第二步：验证Neo4j Bolt协议连接（含身份验证）"""
    print(f"\n=== 第二步：验证Neo4j Bolt连接 {bolt_url} ===")
    driver = None
    try:
        # 初始化驱动
        driver = GraphDatabase.driver(bolt_url, auth=(user, password))
        # 测试连接（执行一个简单的查询）
        with driver.session() as session:
            result = session.run("RETURN 'Connected to Neo4j successfully!' AS message")
            message = result.single()["message"]
            print(f"✅ Neo4j Bolt连接成功！{message}")
            return True
    except exceptions.AuthError:
        print(f"❌ 身份验证失败：用户名/密码错误（当前用户：{user}）")
        return False
    except exceptions.ServiceUnavailable:
        print(f"❌ Neo4j服务不可用：Bolt协议未启用，或Neo4j进程未运行")
        return False
    except exceptions.Neo4jError as e:
        print(f"❌ Neo4j内部错误：{str(e)}")
        return False
    except Exception as e:
        print(f"❌ Bolt连接失败：{str(e)}")
        return False
    finally:
        if driver:
            driver.close()

if __name__ == "__main__":
    # 拆分host和port
    host = "35.208.116.101"
    port = 7687

    # 第一步：端口检测
    port_ok = test_port_connectivity(host, port)
    if not port_ok:
        print("\n❌ 端口不通，无需继续检测Bolt连接")
    else:
        # 第二步：Bolt协议连接检测
        test_neo4j_bolt_connection(NEO4J_BOLT_URL, NEO4J_USER, NEO4J_PASSWORD)