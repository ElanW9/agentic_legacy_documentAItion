CREATE OR REPLACE PACKAGE BODY CUST_MGMT
AS
/******************************************************************************
   NAME:       CUST_MGMT
   PURPOSE:    customer maintenance

   REVISIONS:
   Ver        Date        Author           Description
   ---------  ----------  ---------------  ------------------------------------
   1.0        14/06/2004  RDM              1. Created this package.
   1.1        02/02/2007  RDM              2. credit check
   1.2        19/11/2012  KV               3. gov customers
   1.3        08/05/2016  TM               4. get_cust_attr for invoicing
******************************************************************************/

   V_MAX_LIMIT   CONSTANT NUMBER := 250000;

   /* merge duplicate customers (called from nightly batch) */
   PROCEDURE MERGE_CUST (P_FROM IN NUMBER, P_TO IN NUMBER)
   IS
   BEGIN
      UPDATE ORDERS
         SET CUST_ID = P_TO
       WHERE CUST_ID = P_FROM;

      UPDATE INVOICES
         SET CUST_ID = P_TO
       WHERE CUST_ID = P_FROM;

      UPDATE CUSTOMERS
         SET STATUS = 'C'
       WHERE CUST_ID = P_FROM;
   END MERGE_CUST;


   PROCEDURE CREATE_CUSTOMER (P_NAME    IN  VARCHAR2,
                              P_TYPE    IN  CHAR,
                              P_VAT     IN  VARCHAR2,
                              P_EMAIL   IN  VARCHAR2,
                              P_CTRY    IN  VARCHAR2,
                              P_CUST_ID OUT NUMBER)
   IS
      V_CNT     NUMBER;
      V_LIMIT   NUMBER;
   BEGIN
      UTIL_LOG.SET_CTX('CUST_MGMT');

      IF P_VAT IS NOT NULL THEN
         SELECT COUNT(*)
           INTO V_CNT
           FROM CUSTOMERS
          WHERE VAT_NO = REPLACE(UPPER(P_VAT), ' ', '');

         IF V_CNT > 0 THEN
            RAISE_APPLICATION_ERROR(-20010, 'Customer with VAT ' || P_VAT || ' exists');
         END IF;
      END IF;

      -- default limit: 5000, wholesale 20000
      IF P_TYPE = 'W' THEN
         V_LIMIT := 20000;
      ELSIF P_TYPE = 'G' THEN
         V_LIMIT := NULL;
      ELSE
         V_LIMIT := 2500;
      END IF;

      SELECT SEQ_CUSTOMERS.NEXTVAL INTO P_CUST_ID FROM DUAL;

      INSERT INTO CUSTOMERS (CUST_ID, CUST_NAME, CUST_TYPE, VAT_NO, EMAIL,
                             COUNTRY_CD, CREDIT_LIMIT, STATUS)
           VALUES (P_CUST_ID, P_NAME, NVL(P_TYPE, 'R'), REPLACE(UPPER(P_VAT), ' ', ''),
                   LOWER(P_EMAIL), NVL(P_CTRY, 'BE'), V_LIMIT, 'A');

      UTIL_LOG.LOG_MSG('CREATE', TO_CHAR(P_CUST_ID), 'customer created');
   END CREATE_CUSTOMER;


   PROCEDURE UPD_CREDIT_LIMIT (P_CUST_ID IN NUMBER, P_LIMIT IN NUMBER)
   IS
   BEGIN
      IF P_LIMIT > V_MAX_LIMIT THEN
         RAISE_APPLICATION_ERROR(-20011, 'Limit too high');
      END IF;

      UPDATE CUSTOMERS
         SET CREDIT_LIMIT = P_LIMIT
       WHERE CUST_ID = P_CUST_ID
         AND STATUS <> 'C';

      UTIL_LOG.LOG_MSG('UPD_LIMIT', TO_CHAR(P_CUST_ID), 'new limit ' || P_LIMIT);
   EXCEPTION
      WHEN OTHERS THEN
         NULL;
   END UPD_CREDIT_LIMIT;


   PROCEDURE BLOCK_CUSTOMER (P_CUST_ID IN NUMBER, P_REASON IN VARCHAR2)
   IS
   BEGIN
      UPDATE CUSTOMERS
         SET STATUS = 'B',
             BLOCKED_REASON = SUBSTR(P_REASON, 1, 200)
       WHERE CUST_ID = P_CUST_ID;

      -- put open orders on hold
      UPDATE ORDERS
         SET ORD_STATUS = 15
       WHERE CUST_ID = P_CUST_ID
         AND ORD_STATUS IN (10, 20);

      UTIL_LOG.LOG_MSG('BLOCK', TO_CHAR(P_CUST_ID), P_REASON, 'W');
      COMMIT;
   END BLOCK_CUSTOMER;


   PROCEDURE UNBLOCK_CUSTOMER (P_CUST_ID IN NUMBER)
   IS
   BEGIN
      UPDATE CUSTOMERS
         SET STATUS = 'A',
             BLOCKED_REASON = NULL
       WHERE CUST_ID = P_CUST_ID
         AND STATUS = 'B';

      UTIL_LOG.LOG_MSG('UNBLOCK', TO_CHAR(P_CUST_ID), NULL);
   END UNBLOCK_CUSTOMER;


   FUNCTION GET_CUST_TYPE (P_CUST_ID IN NUMBER) RETURN CHAR
   IS
      V_TYPE   CUSTOMERS.CUST_TYPE%TYPE;
   BEGIN
      SELECT CUST_TYPE
        INTO V_TYPE
        FROM CUSTOMERS
       WHERE CUST_ID = P_CUST_ID;

      RETURN V_TYPE;
   EXCEPTION
      WHEN NO_DATA_FOUND THEN
         RETURN 'R';
   END GET_CUST_TYPE;


   -- check if customer can place order of P_AMT
   FUNCTION CHK_CREDIT (P_CUST_ID IN NUMBER, P_AMT IN NUMBER) RETURN NUMBER
   IS
      V_LIMIT    CUSTOMERS.CREDIT_LIMIT%TYPE;
      V_STATUS   CUSTOMERS.STATUS%TYPE;
      V_TYPE     CUSTOMERS.CUST_TYPE%TYPE;
      V_OPEN     NUMBER;
   BEGIN
      SELECT CREDIT_LIMIT, STATUS, CUST_TYPE
        INTO V_LIMIT, V_STATUS, V_TYPE
        FROM CUSTOMERS
       WHERE CUST_ID = P_CUST_ID;

      IF V_STATUS <> 'A' THEN
         RETURN 0;
      END IF;

      IF V_TYPE = 'G' THEN
         RETURN 1;
      END IF;

      V_OPEN := INV_API.GET_OPEN_AMT(P_CUST_ID);

      IF V_LIMIT IS NULL OR V_OPEN + P_AMT <= V_LIMIT * 1.1 THEN
         RETURN 1;
      ELSE
         RETURN 0;
      END IF;
   EXCEPTION
      WHEN NO_DATA_FOUND THEN
         RETURN 0;
   END CHK_CREDIT;


   FUNCTION GET_BALANCE (P_CUST_ID IN NUMBER) RETURN NUMBER
   IS
   BEGIN
      RETURN GET_BALANCE(P_CUST_ID, SYSDATE);
   END GET_BALANCE;


   -- balance = invoiced - paid
   FUNCTION GET_BALANCE (P_CUST_ID IN NUMBER, P_AS_OF IN DATE) RETURN NUMBER
   IS
      V_INV   NUMBER;
      V_PAY   NUMBER;
   BEGIN
      SELECT NVL(SUM(GROSS_AMT), 0)
        INTO V_INV
        FROM INVOICES
       WHERE CUST_ID = P_CUST_ID
         AND INV_DT <= P_AS_OF
         AND INV_STATUS <> 'CANC';

      SELECT NVL(SUM(P.PAY_AMT), 0)
        INTO V_PAY
        FROM PAYMENTS P, INVOICES I
       WHERE P.INV_ID = I.INV_ID
         AND I.CUST_ID = P_CUST_ID
         AND P.PAY_DT <= P_AS_OF;

      RETURN V_INV - V_PAY;
   END GET_BALANCE;


   -- generic getter, used by reports
   FUNCTION GET_CUST_ATTR (P_CUST_ID IN NUMBER, P_COL IN VARCHAR2) RETURN VARCHAR2
   IS
      V_VAL   VARCHAR2(4000);
   BEGIN
      EXECUTE IMMEDIATE 'SELECT TO_CHAR(' || P_COL || ') FROM CUSTOMERS WHERE CUST_ID = :1'
         INTO V_VAL
         USING P_CUST_ID;

      RETURN V_VAL;
   EXCEPTION
      WHEN OTHERS THEN
         RETURN NULL;
   END GET_CUST_ATTR;


   -- nightly: block customers with invoices > 60 days overdue
   PROCEDURE CHK_OVERDUE_CUSTOMERS
   IS
      CURSOR C_OVD
      IS
         SELECT DISTINCT CUST_ID
           FROM V_OPEN_INVOICES
          WHERE DAYS_OVERDUE > 90;
   BEGIN
      FOR R IN C_OVD
      LOOP
         IF GET_CUST_TYPE(R.CUST_ID) <> 'G' THEN
            BLOCK_CUSTOMER(R.CUST_ID, 'AUTO: overdue invoices');
         END IF;
      END LOOP;
   END CHK_OVERDUE_CUSTOMERS;

END CUST_MGMT;
/
