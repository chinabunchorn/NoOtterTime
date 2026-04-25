# PostgreSQL Migration Guide

Your Flask application has been successfully migrated from SQLite to PostgreSQL. This guide covers the changes made and how to set up your Render deployment.

## Changes Made

### 1. **database.py** - Database Connection & Initialization
- **New imports**: `psycopg2` and `urllib.parse.urlparse` 
- **Added `get_db_connection()`**: Parses `DATABASE_URL` environment variable to connect to PostgreSQL
- **Updated `init_db()`**: Uses PostgreSQL syntax with:
  - `SERIAL` instead of `INTEGER PRIMARY KEY AUTOINCREMENT`
  - `TIMESTAMP` instead of `DATETIME`
  - `ON DELETE CASCADE` for foreign keys (ensures referential integrity)
  - Proper `NOT NULL` constraints

### 2. **managers.py** - Database Query Updates
- **Imports**: Changed from `sqlite3` to `psycopg2` with `RealDictCursor`
- **BaseManager class**:
  - Now uses `get_db_connection()` from database.py
  - Added `_get_cursor()` method for consistency
- **All SQL queries updated**:
  - Parameter placeholders: `?` → `%s`
  - Last insert ID: `cursor.lastrowid` → `RETURNING id` clause
  - Date functions:
    - `STRFTIME('%Y', column)` → `EXTRACT(YEAR FROM column)::INT`
    - `STRFTIME('%W', column)` → `TO_CHAR(column, 'WW')::INT`
    - `date('now', '...')` → `NOW() - INTERVAL '... days'`
    - `STRFTIME('%w', column)` → `EXTRACT(DOW FROM column)::INT`

### 3. **requirements.txt** - Dependencies
Added:
- **psycopg2-binary==2.9.10** - PostgreSQL adapter for Python
- **gunicorn==23.0.0** - Production WSGI server for Render

### 4. **app_controller.py** - Cleanup
- Removed unused `sqlite3` import

## Local Development Setup

### Option 1: PostgreSQL Installed Locally
```bash
# Install/update packages
pip install -r requirements.txt

# Create local PostgreSQL database
createdb nootter_time

# Set DATABASE_URL (Windows PowerShell)
$env:DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/nootter_time"

# Or (Windows Command Prompt)
set DATABASE_URL=postgresql://postgres:postgres@localhost:5432/nootter_time

# Or (Linux/Mac)
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/nootter_time

# Run your app
python app_controller.py
```

### Option 2: Docker PostgreSQL
```bash
# Start PostgreSQL container
docker run --name nootter-postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=nootter_time \
  -p 5432:5432 \
  -d postgres:15

# Set DATABASE_URL to: postgresql://postgres:postgres@localhost:5432/nootter_time
```

## Render Deployment Setup

### Step 1: Create PostgreSQL Database on Render
1. Go to [render.com](https://render.com)
2. Click "New +" → "PostgreSQL"
3. Fill in the details:
   - **Name**: `NoOtterTime` (or your choice)
   - **Database**: `nootter_time`
   - **User**: `postgres`
   - **Region**: Choose closest to you
4. Create the database and copy the external database URL

### Step 2: Create Flask Web Service on Render
1. Click "New +" → "Web Service"
2. Connect your GitHub repository
3. Fill in the details:
   - **Name**: `nootter-time` (or your choice)
   - **Environment**: `Python 3`
   - **Region**: Same as database
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app_controller:AppController().get_app()`
4. Add environment variable:
   - **Key**: `DATABASE_URL`
   - **Value**: Paste the Postgres URL from Step 1

### Step 3: Update app_controller.py for Gunicorn
Add this method to your `AppController` class to expose the Flask app:

```python
def get_app(self):
    """Returns the Flask app instance for Gunicorn."""
    return self._app
```

Or change the last line of your main execution block to:

```python
if __name__ == "__main__":
    app_controller = AppController()
    app_controller._app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
```

### Step 4: Deploy
1. Push code changes to GitHub
2. Render will auto-deploy on push
3. Monitor deployment logs in the Render dashboard

## DATABASE_URL Format

PostgreSQL connection string format:
```
postgresql://[user]:[password]@[host]:[port]/[database]
```

Examples:
- Local: `postgresql://postgres:postgres@localhost:5432/nootter_time`
- Render: `postgresql://nootter_time_user:xxxxx@dpg-xxxxx.postgres.render.com/nootter_time`

## Troubleshooting

### Connection Issues
- Ensure `DATABASE_URL` is set correctly in your environment
- Check that PostgreSQL is running
- Verify database name and credentials

### Migration Issues
- All table names, columns are the same
- Data types are compatible
- Foreign key constraints are tighter (good for data integrity)

### Performance Tips
1. Add indexes for frequently queried columns:
   ```sql
   CREATE INDEX idx_user_id ON study_sessions(user_id);
   CREATE INDEX idx_course_id ON study_sessions(course_id);
   CREATE INDEX idx_start_time ON study_sessions(start_time);
   ```

2. Connection pooling (optional for production):
   - Add `pgbouncer` or use connection pooling in Render

## Differences from SQLite
- PostgreSQL is more strict about types
- Better handling of concurrent connections
- More robust for production use
- Better support for complex queries

No code changes needed - everything is backward compatible!
