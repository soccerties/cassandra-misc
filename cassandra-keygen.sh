#!/bin/sh

set -e

OUTPUT_DIR="./keys"
# Password to unlock CA key
CA_OUT_PASSWORD="1234"
# Password to unlock node keystore and private key
KEYSTORE_PASS="keypass"
# Password for CA cert truststore to validate certs
TRUSTSTORE_PASS="trustpass"
CERT_VALIDITY=1095 # in days
CA_VALIDITY=1095   # in days
ROOT_CN="ABC-rootCA"
CERT_OU="Cassandra"
CERT_O="ABC-Company"
CERT_C="US"
KEYSIZE=2048
SAN_EXTENSION="IP"
CLUSTER_NODES="$@"

KEYTOOL=`which keytool`

create_cert_authority()
{
  if [ -f "$OUTPUT_DIR/$ROOT_CN.key" ]; then
     INPUT=""
     while [ -z "$INPUT" ]
     do
      read -p "Certificate Authority $ROOT_CN key already exists. Overwrite it? (y|n)" INPUT
      case "$INPUT" in
        y)
          delete_cert_authority
          echo "***** Old Certificate Authority Deleted."
          echo "***** Any node keystores created with the old CA need to be recreated!";;
        n)
          return;;
        *)
          echo "unknown input"
          INPUT="";;
        esac
     done
  fi
  openssl req -new -x509 -subj /CN=$ROOT_CN/OU=$CERT_OU/O=$CERT_O/C=$CERT_C/ \
    -keyout "$OUTPUT_DIR/$ROOT_CN.key" -out "$OUTPUT_DIR/$ROOT_CN.crt" \
    -days $CA_VALIDITY -passout pass:$CA_OUT_PASSWORD
  $KEYTOOL -importcert -keystore "$OUTPUT_DIR/server-truststore.jks" \
    -alias $ROOT_CN -file "$OUTPUT_DIR/$ROOT_CN.crt" -noprompt -storepass "${TRUSTSTORE_PASS}"
}

delete_cert_authority()
{
  rm -f "$OUTPUT_DIR/$ROOT_CN.key"
  rm -f "$OUTPUT_DIR/$ROOT_CN.crt"
  rm -f "$OUTPUT_DIR/server-truststore.jks"
}

create_node_keystore()
{
  node=$1

  if [ -f "$OUTPUT_DIR/$node.jks" ]; then
     INPUT=""
     while [ -z "$INPUT" ]
     do
      read -p "$node keystore already exists. Overwrite it? (y|n)" INPUT
      case "$INPUT" in
        y)
          rm -f "$OUTPUT_DIR/$node.jks" ;;
        n)
          return;;
        *)
          echo "unknown input"
          INPUT="";;
        esac
     done
  fi

  echo "Creating key pair for $node"
  $KEYTOOL -genkeypair -keyalg RSA -alias $node -keystore "$OUTPUT_DIR/$node.jks" \
    -storepass "${KEYSTORE_PASS}" -keypass "${KEYSTORE_PASS}" -validity $CERT_VALIDITY -deststoretype pkcs12 \
    -keysize $KEYSIZE -dname "CN=$node, OU=$CERT_OU, O=$CERT_O, C=$CERT_C" -ext "SAN=$SAN_EXTENSION:$node"

  echo "Adding CA cert to $node keystore"
  $KEYTOOL -importcert -keystore "$OUTPUT_DIR/$node.jks" -alias $ROOT_CN -file "$OUTPUT_DIR/$ROOT_CN.crt" -noprompt \
    -storepass "${KEYSTORE_PASS}" -keypass "${KEYSTORE_PASS}"

  echo "Generating CSR for $node"
  $KEYTOOL -certreq -keystore "$OUTPUT_DIR/$node.jks" -alias $node -file "$OUTPUT_DIR/$node.csr" -storepass "${KEYSTORE_PASS}" \
    -keypass "${KEYSTORE_PASS}" -dname "CN=$node, OU=$CERT_OU, O=$CERT_O, C=$CERT_C" -ext "SAN=$SAN_EXTENSION:$node"

  #temp file to add SAN extensions to the signed cert
  echo "[ext]\nsubjectAltName = $SAN_EXTENSION:$node" > "$OUTPUT_DIR/extensions.tmp"

  echo "Signing CSR for $node"
  openssl x509 -req -CA "$OUTPUT_DIR/$ROOT_CN.crt" -CAkey "$OUTPUT_DIR/$ROOT_CN.key" -in "$OUTPUT_DIR/$node.csr" \
    -out "$OUTPUT_DIR/$node.crt_signed" -days $CERT_VALIDITY -CAcreateserial -passin pass:"${CA_OUT_PASSWORD}" \
    -extfile "$OUTPUT_DIR/extensions.tmp" -extensions ext

  rm -f "$OUTPUT_DIR/extensions.tmp"

  echo "Verifying signed cert for $node"
  openssl verify -CAfile "$OUTPUT_DIR/$ROOT_CN.crt" "$OUTPUT_DIR/$node.crt_signed"

  echo "Importing signed CRT for $node"
  $KEYTOOL -importcert -keystore "$OUTPUT_DIR/$node.jks" -alias $node -file "$OUTPUT_DIR/$node.crt_signed" \
    -noprompt -storepass "${KEYSTORE_PASS}" -keypass "${KEYSTORE_PASS}"

  $KEYTOOL -list -keystore "$OUTPUT_DIR/$node.jks" -storepass "${KEYSTORE_PASS}"
}


mkdir -p $OUTPUT_DIR

create_cert_authority

if [ -n "$CLUSTER_NODES" ]; then
  for node in ${CLUSTER_NODES};
  do
    create_node_keystore $node
    echo "---"
  done
else
  echo "No nodes passed to create keys for."
  echo "Pass in one or more hostnames separated by spaces to create keys"
fi
