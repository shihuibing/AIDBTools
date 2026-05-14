import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.ResultSetMetaData;
import java.sql.SQLException;
import java.sql.Statement;

public class XuguJdbcBridge {
    private static String env(String key, String defaultValue) {
        String value = System.getenv(key);
        return value == null ? defaultValue : value;
    }

    private static String readSqlFromStdin() throws Exception {
        BufferedReader reader = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
        StringBuilder sb = new StringBuilder();
        String line;
        boolean first = true;
        while ((line = reader.readLine()) != null) {
            if (!first) {
                sb.append('\n');
            }
            sb.append(line);
            first = false;
        }
        return sb.toString().trim();
    }

    private static String jsonString(String value) {
        if (value == null) {
            return "null";
        }
        StringBuilder sb = new StringBuilder();
        sb.append('"');
        for (int i = 0; i < value.length(); i++) {
            char ch = value.charAt(i);
            switch (ch) {
                case '"':
                    sb.append("\\\"");
                    break;
                case '\\':
                    sb.append("\\\\");
                    break;
                case '\b':
                    sb.append("\\b");
                    break;
                case '\f':
                    sb.append("\\f");
                    break;
                case '\n':
                    sb.append("\\n");
                    break;
                case '\r':
                    sb.append("\\r");
                    break;
                case '\t':
                    sb.append("\\t");
                    break;
                default:
                    if (ch < 0x20) {
                        sb.append(String.format("\\u%04x", (int) ch));
                    } else {
                        sb.append(ch);
                    }
                    break;
            }
        }
        sb.append('"');
        return sb.toString();
    }

    private static String buildErrorMessage(Throwable throwable) {
        StringBuilder sb = new StringBuilder();
        Throwable current = throwable;
        boolean first = true;
        while (current != null) {
            String part = current.getMessage();
            if (part == null || part.isBlank()) {
                part = current.getClass().getSimpleName();
            }
            if (!first) {
                sb.append(" | ");
            }
            sb.append(part.trim());
            first = false;
            current = current.getCause();
        }
        return sb.toString();
    }

    private static void writeError(Throwable throwable) {
        System.out.println("{\"ok\":false,\"error\":" + jsonString(buildErrorMessage(throwable)) + "}");
    }

    private static void writeSuccessNoRows(int updateCount) {
        System.out.println("{\"ok\":true,\"returnsRows\":false,\"updateCount\":" + updateCount + ",\"columns\":[],\"rows\":[]}");
    }

    private static void writeSuccessRows(ResultSet rs) throws SQLException {
        ResultSetMetaData meta = rs.getMetaData();
        int columnCount = meta.getColumnCount();
        StringBuilder sb = new StringBuilder();
        sb.append("{\"ok\":true,\"returnsRows\":true,\"columns\":[");
        for (int i = 1; i <= columnCount; i++) {
            if (i > 1) {
                sb.append(',');
            }
            sb.append(jsonString(meta.getColumnLabel(i)));
        }
        sb.append("],\"rows\":[");

        boolean firstRow = true;
        while (rs.next()) {
            if (!firstRow) {
                sb.append(',');
            }
            sb.append('[');
            for (int i = 1; i <= columnCount; i++) {
                if (i > 1) {
                    sb.append(',');
                }
                Object value = rs.getObject(i);
                sb.append(jsonString(value == null ? null : String.valueOf(value)));
            }
            sb.append(']');
            firstRow = false;
        }
        sb.append("]}");
        System.out.println(sb);
    }

    public static void main(String[] args) {
        String host = env("XUGU_HOST", "127.0.0.1").trim();
        String port = env("XUGU_PORT", "5138").trim();
        String user = env("XUGU_USER", "");
        String password = env("XUGU_PASSWORD", "");
        String dbname = env("XUGU_DBNAME", "").trim();

        try {
            String sql = readSqlFromStdin();
            if (sql == null || sql.isBlank()) {
                throw new IllegalArgumentException("SQL 为空");
            }

            String url = dbname.isEmpty()
                    ? "jdbc:xugu://" + host + ":" + port + "/"
                    : "jdbc:xugu://" + host + ":" + port + "/" + dbname;

            Class.forName("com.xugu.cloudjdbc.Driver");
            DriverManager.setLoginTimeout(5);

            try (Connection conn = DriverManager.getConnection(url, user, password);
                 Statement stmt = conn.createStatement()) {
                conn.setAutoCommit(false);
                try {
                    stmt.setQueryTimeout(30);
                } catch (Throwable ignore) {
                }

                boolean hasResultSet = stmt.execute(sql);
                if (hasResultSet) {
                    try (ResultSet rs = stmt.getResultSet()) {
                        writeSuccessRows(rs);
                    }
                } else {
                    conn.commit();
                    writeSuccessNoRows(stmt.getUpdateCount());
                }
            }
        } catch (Throwable throwable) {
            writeError(throwable);
            System.exit(1);
        }
    }
}
