from upstash_redis import Redis
import time

# Initialize the Redis client
redis_client = Redis(
    url="https://tops-sparrow-26652.upstash.io",  # Replace with your Upstash Redis URL
    token="xxx"             # Replace with your Upstash token
)

# Maximum allowed submissions per IP within the time window
MAX_SUBMISSIONS = 2
TIME_WINDOW = 60   # 5 minutes in seconds

ip_address = "127.0.0.1"  # Get the user's IP address
ip_record = redis_client.get(ip_address)
current_time = time.time()

print("ip_record: " + str(ip_record))
#redis_client.delete(ip_address)

# Track submissions per session
if ip_record == None:
    print("ip_record doesn't exist")
    redis_client.set(ip_address, "1-"+str(current_time))
else:
    attempt_count = int(ip_record[0])
    split_string = ip_record.split("-")  # Split by the hyphen
    first_attempt = split_string[1]  # Access the second element (the first timestamp)
    time_stamps = ip_record[ip_record.find("-") + 1:]  # Slice everything after the first hyphen
    print("attempt count: " + str(attempt_count))
    print("first_attempt: " + first_attempt)
    time_elapsed = current_time - float(first_attempt)
    print("time_difference: " + str(time_elapsed))
    if time_elapsed > TIME_WINDOW:
        print("time elapsed, setting ip_address record to zero")
        redis_client.set(ip_address, "1-" + str(current_time))
    elif attempt_count<=MAX_SUBMISSIONS:
        redis_client.set(ip_address, str(attempt_count+1) + "-" + time_stamps + "-" + str(current_time))
        print("time didn't elapse, add another timestamp.  New record value: " + str(redis_client.get(ip_address)))
    else:
        print("Submission limit exceeded. Please try again later.")

# # Test the connection
# try:
#     redis_client.set("test_key", 0)
#     value = redis_client.get("test_key")
#
#     if value == None:
#         print(f"Key in Redis does not exist")
#     else:
#         print(f"Value from Redis: " + str(value))
# except Exception as e:
#     print(f"Error connecting to Upstash Redis: {e}")
