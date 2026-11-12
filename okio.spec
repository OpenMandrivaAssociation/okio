Name:		okio
Version:	3.6.0
Release:	1
Summary:	Modern I/O library for Java and Kotlin
Group:		Development/Java
License:	Apache-2.0
URL:		https://github.com/square/okio
# Square tag parent-3.6.0. The JVM jar is commonMain plus jvmMain.
# kotlinc 2.0.21 rejects expect constructors that use default arguments
# when the actual is a typealias, so those constructors are split into
# overloads. IOException, EOFException, and FileNotFoundException stay
# typealiases of the java.io classes.
Source0:	okio-%{version}.tar.gz
Patch0:		okio-expect-constructors.patch

BuildArch:	noarch
BuildRequires:	java-21-openjdk-devel
BuildRequires:	kotlin
BuildRequires:	sysjar
BuildRequires:	javapackages-filesystem
BuildRequires:	mvn(org.jetbrains.kotlin:kotlin-stdlib)
BuildRequires:	mvn(org.jetbrains.kotlin:kotlin-stdlib-jdk7)
BuildRequires:	mvn(org.jetbrains.kotlin:kotlin-stdlib-jdk8)

%description
com.squareup.okio:okio %{version}. Buffer and ByteString for byte streams.
The JVM sources are compiled with the installed kotlinc.

%prep
%autosetup -n okio-%{version} -p1
find . -type f \( -name '*.jar' -o -name '*.class' -o -name '*.so' -o -name '*.node' -o -name '*.wasm' \) -print > binaries.list
find . -type d -name '*.jar' -print >> binaries.list
if [ -s binaries.list ]; then
	cat binaries.list
	exit 1
fi
grep -F -q 'constructor()' okio/src/commonMain/kotlin/okio/CommonPlatform.kt
if grep -F -q 'String? = null' okio/src/commonMain/kotlin/okio/CommonPlatform.kt; then
	exit 1
fi
test "$(find okio/src/commonMain okio/src/jvmMain -name '*.kt' | wc -l)" -eq 77

%build
set -eo pipefail
export JAVA_HOME=%{_jvmdir}/java-21-openjdk
export PATH="$JAVA_HOME/bin:/usr/bin:/bin"
CPSTD=%{_javadir}/kotlin-stdlib.jar
CPJDK7=%{_javadir}/kotlin-stdlib-jdk7.jar
CPJDK8=%{_javadir}/kotlin-stdlib-jdk8.jar
test -s "$CPSTD"
test -s "$CPJDK7"
test -s "$CPJDK8"
find okio/src/commonMain -name '*.kt' > common.list
find okio/src/commonMain okio/src/jvmMain -name '*.kt' > kt.list
test "$(wc -l < kt.list)" -eq 77
common=$(paste -sd, common.list)
mkdir -p classes
kotlinc -J-Xmx2g -jvm-target 1.8 -language-version 1.9 -Xmulti-platform -Xexpect-actual-classes \
	-Xcommon-sources="$common" \
	-cp "$CPSTD:$CPJDK7:$CPJDK8" \
	-d classes @kt.list
test -s classes/okio/Buffer.class
test -s classes/okio/ByteString.class
if [ -e classes/okio/IOException.class ]; then
	exit 1
fi
test "$(find classes -name '*.class' | wc -l)" -eq 107
javap -v -classpath classes okio.Buffer | grep -F -q 'major version: 52'
printf '%s\n' 'Manifest-Version: 1.0' 'Automatic-Module-Name: okio' "Implementation-Version: %{version}" > manifest.mf
jar cfm okio.jar manifest.mf -C classes .
jar i okio.jar
desc=$(jar --describe-module --file okio.jar)
printf '%s\n' "$desc"
printf '%s\n' "$desc" | grep -F -q ' okio'
if printf '%s\n' "$desc" | grep -F -q 'Unable'; then
	exit 1
fi

cat > okio.pom << END
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.squareup.okio</groupId>
  <artifactId>okio</artifactId>
  <version>%{version}</version>
  <name>okio</name>
  <description>A modern I/O library for Java and Kotlin.</description>
  <url>https://github.com/square/okio</url>
  <licenses>
    <license>
      <name>Apache-2.0</name>
      <url>https://www.apache.org/licenses/LICENSE-2.0.txt</url>
    </license>
  </licenses>
  <dependencies>
    <dependency>
      <groupId>org.jetbrains.kotlin</groupId>
      <artifactId>kotlin-stdlib</artifactId>
      <version>2.0.21</version>
    </dependency>
  </dependencies>
</project>
END

%install
set -eo pipefail
sysjar install --buildroot %{buildroot} \
	--artifact okio.pom:okio.jar \
	--file-name okio \
	--filelist .mfiles
idx="%{buildroot}/usr/share/sysjar/index/com.squareup.okio/okio.sysjar"
test -s "$idx"
grep -F -q '"version": "%{version}"' "$idx"
grep -F -q '"artifactId": "okio"' "$idx"
test -s %{buildroot}%{_javadir}/okio.jar

%check
set -eo pipefail
export JAVA_HOME=%{_jvmdir}/java-21-openjdk
export PATH="$JAVA_HOME/bin:/usr/bin:/bin"
JAR=%{buildroot}%{_javadir}/okio.jar
test -s "$JAR"
STDLIB=%{_javadir}/kotlin-stdlib.jar:%{_javadir}/kotlin-stdlib-jdk7.jar:%{_javadir}/kotlin-stdlib-jdk8.jar
mkdir -p check
cat > check/Check.kt << 'EOF'
import okio.Buffer

fun main() {
    val buffer = Buffer()
    buffer.writeUtf8("okio")
    val text = buffer.readUtf8()
    if (text != "okio" || buffer.size != 0L) {
        error(text + " " + buffer.size)
    }
    println("okio_ok " + text)
}
EOF
kotlinc -J-Xmx1g -jvm-target 1.8 -language-version 1.9 \
	-cp "$JAR:$STDLIB" -d check/out check/Check.kt
java -cp "check/out:$JAR:$STDLIB" CheckKt > check/out.txt
cat check/out.txt
grep -F -qx 'okio_ok okio' check/out.txt

%files -f .mfiles
%license LICENSE.txt
