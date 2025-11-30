import os
import httpx
import pandas as pd
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

AMAP_API_KEY = os.getenv("AMAP_API_KEY")
AMAP_ADCODE_FILE = "tools/AMap_adcode_citycode.xlsx"

# 初始化 MCP 服务
mcp = FastMCP("WeatherService")

# 加载城市编码表
df_city = None
try:
    # 获取当前脚本所在目录 (tools/)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # 获取项目根目录
    root_dir = os.path.dirname(base_dir)
    file_path = os.path.join(root_dir, AMAP_ADCODE_FILE)
    
    if os.path.exists(file_path):
        # 指定 dtype={'adcode': str} 以防止前导零丢失
        df_city = pd.read_excel(file_path, dtype={'adcode': str})
    else:
        print(f"Warning: {file_path} not found.")
except Exception as e:
    print(f"Error loading city codes: {e}")

def get_adcode(city_name: str) -> str:
    if df_city is None:
        return None
    
    # 1. 尝试精确匹配中文名
    match = df_city[df_city['中文名'] == city_name]
    if not match.empty:
        return match.iloc[0]['adcode']
    
    # 2. 尝试模糊匹配 (例如 "南京" -> "南京市")
    # 过滤掉无效数据
    valid_cities = df_city[df_city['中文名'].notna()]
    match = valid_cities[valid_cities['中文名'].str.contains(city_name)]
    
    if not match.empty:
        # 优先选择 "市" 结尾的，如果有很多匹配
        # 比如搜 "朝阳"，可能有 "朝阳区" (北京) 和 "朝阳市" (辽宁)
        # 这里简单取第一个，或者可以根据长度排序
        return match.iloc[0]['adcode']
        
    return None

@mcp.tool()
async def get_weather(city: str) -> str:
    """
    查询指定城市的天气信息（包含实时天气和预报）。
    
    Args:
        city: 城市中文名称（例如："南京", "北京"）
    """
    if not AMAP_API_KEY or AMAP_API_KEY == "your_amap_api_key_here":
        return "Error: AMAP_API_KEY not configured in .env file."
        
    adcode = get_adcode(city)
    if not adcode:
        return f"Error: Could not find adcode for city '{city}'. Please try a more specific name (e.g., '南京市')."

    async with httpx.AsyncClient() as client:
        try:
            base_url = "https://restapi.amap.com/v3/weather/weatherInfo"
            
            # 1. 获取实时天气 (base)
            base_params = {
                "key": AMAP_API_KEY,
                "city": adcode,
                "extensions": "base",
                "output": "JSON"
            }
            resp_base = await client.get(base_url, params=base_params)
            data_base = resp_base.json()
            
            if data_base.get("status") != "1":
                return f"Error fetching live weather: {data_base.get('info')}"
            
            lives = data_base.get("lives", [])
            if not lives:
                return f"No live weather data found for {city}."
            
            live_data = lives[0]
            
            # 2. 获取预报天气 (all)
            all_params = {
                "key": AMAP_API_KEY,
                "city": adcode,
                "extensions": "all",
                "output": "JSON"
            }
            resp_all = await client.get(base_url, params=all_params)
            data_all = resp_all.json()
            
            if data_all.get("status") != "1":
                # 如果预报失败，至少返回实况
                return f"Live Weather: {live_data.get('weather')}, {live_data.get('temperature')}C. (Forecast fetch failed)"
                
            forecasts = data_all.get("forecasts", [])
            if not forecasts:
                return f"Live Weather: {live_data.get('weather')}, {live_data.get('temperature')}C. (No forecast data)"
                
            forecast_data = forecasts[0]
            casts = forecast_data.get("casts", [])
            if not casts:
                return f"Live Weather: {live_data.get('weather')}, {live_data.get('temperature')}C. (No casts data)"
            
            # 3. 组合结果
            # 构建实况信息
            output_lines = [
                f"【{live_data.get('city')} 实时天气】",
                f"天气: {live_data.get('weather')}",
                f"气温: {live_data.get('temperature')}℃",
                f"更新时间: {live_data.get('reporttime')}",
                "",
                f"【未来天气预报】"
            ]

            # 遍历所有预报数据 (通常包含当天及未来3天)
            for cast in casts:
                date_str = cast.get('date')
                week_str = cast.get('week')
                day_weather = cast.get('dayweather')
                night_weather = cast.get('nightweather')
                day_temp = cast.get('daytemp')
                night_temp = cast.get('nighttemp')
                
                cast_line = (
                    f"- {date_str} (星期{week_str}): "
                    f"白天{day_weather}/{day_temp}℃, "
                    f"晚上{night_weather}/{night_temp}℃。 "
                )
                output_lines.append(cast_line)
            
            return "\n".join(output_lines)

        except Exception as e:
            return f"Exception during weather query: {str(e)}"

if __name__ == "__main__":
    # 这是 MCP Server 的标准入口，它会接管 Stdin/Stdout
    mcp.run()