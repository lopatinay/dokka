# dokka

## Running the Project
Build and Start the Containers:

```bash
docker-compose up -d
```

## API

### calculateDistances
```bash
curl --location 'http://127.0.0.1:5000/api/calculateDistances' \
--form 'file=@"testdata.csv"'
```
response:
```json
{
    "message": "File uploaded and tasks created successfully",
    "task_status": "pending",
    "upload_uuid": "0c4e4788-39b6-40ba-b489-64f05ed7813e"
}
```

### getResult
use `upload_uuid` as path param for the getting task result
```bash
curl --location 'http://127.0.0.1:5000/api/getResult/0c4e4788-39b6-40ba-b489-64f05ed7813e'
```

### Calc distance in runtime
```bash
curl --location 'http://127.0.0.1:5000/api/runtime-distance' \
--form 'file=@"testdata.csv"'
```