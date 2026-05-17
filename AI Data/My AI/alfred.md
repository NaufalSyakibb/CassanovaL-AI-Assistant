# Conversation History — task

## 2026-05-12 23:48:34

**You:** cara membuat constructor

**task:** "**Constructor**" adalah metode khusus dalam pemrograman berorientasi objek (OOP) yang digunakan untuk **menginisialisasi objek** saat pertama kali dibuat. Constructor memiliki nama yang sama dengan nama kelasnya dan tidak memiliki nilai pengembalian (return type).

Berikut adalah cara membuat constructor dalam beberapa bahasa pemrograman populer:

---

### **1. Java**
Di Java, constructor didefinisikan dengan nama yang sama persis dengan nama kelasnya. Constructor dapat memiliki parameter atau tidak (default constructor).

#### Contoh:
```java
public class Mobil {
    String merk;
    int tahun;

    // Constructor tanpa parameter (default constructor)
    public Mobil() {
        merk = "Toyota";
        tahun = 2020;
    }

    // Constructor dengan parameter
    public Mobil(String merk, int tahun) {
        this.merk = merk;
        this.tahun = tahun;
    }
}
```

#### Cara penggunaan:
```java
Mobil mobil1 = new Mobil(); // Memanggil default constructor
Mobil mobil2 = new Mobil("Honda", 2022); // Memanggil constructor dengan parameter
```

---

### **2. Python**
Di Python, constructor didefinisikan dengan metode `__init__`.

#### Contoh:
```python
class Mobil:
    def __init__(self, merk="Toyota", tahun=2020):
        self.merk = merk
        self.tahun = tahun
```

#### Cara penggunaan:
```python
mobil1 = Mobil()  # Menggunakan nilai default
mobil2 = Mobil("Honda", 2022)  # Menggunakan nilai yang ditentukan
```

---

### **3. C++**
Di C++, constructor memiliki nama yang sama dengan nama kelasnya dan tidak memiliki tipe pengembalian.

#### Contoh:
```cpp
#include <iostream>
#include <string>
using namespace std;

class Mobil {
public:
    string merk;
    int tahun;

    // Constructor tanpa parameter
    Mobil() {
        merk = "Toyota";
        tahun = 2020;
    }

    // Constructor dengan parameter
    Mobil(string merk, int tahun) {
        this->merk = merk;
        this->tahun = tahun;
    }
};
```

#### Cara penggunaan:
```cpp
Mobil mobil1; // Memanggil default constructor
Mobil mobil2("Honda", 2022); // Memanggil constructor dengan parameter
```

---

### **4. JavaScript (ES6)**
Di JavaScript, constructor didefinisikan menggunakan metode `constructor` dalam kelas.

#### Contoh:
```javascript
class Mobil {
    constructor(merk = "Toyota", tahun = 2020) {
        this.merk = merk;
        this.tahun = tahun;
    }
}
```

#### Cara penggunaan:
```javascript
const mobil1 = new Mobil(); // Menggunakan nilai default
const mobil2 = new Mobil("Honda", 2022); // Menggunakan nilai yang ditentukan
```

---

### **5. C#**
Di C#, constructor didefinisikan dengan nama yang sama dengan nama kelasnya.

#### Contoh:
```csharp
using System;

class Mobil {
    public string merk;
    public int tahun;

    // Constructor tanpa parameter
    public Mobil() {
        merk = "Toyota";
        tahun = 2020;
    }

    // Constructor dengan parameter
    public Mobil(string merk, int tahun) {
        this.merk = merk;
        this.tahun = tahun;
    }
}
```

#### Cara penggunaan:
```csharp
Mobil mobil1 = new Mobil(); // Memanggil default constructor
Mobil mobil2 = new Mobil("Honda", 2022); // Memanggil constructor dengan parameter
```

---

### **6. PHP**
Di PHP, constructor didefinisikan dengan metode `__construct`.

#### Contoh:
```php
<?php
class Mobil {
    public $merk;
    public $tahun;

    // Constructor
    public function __construct($merk = "Toyota", $tahun = 2020) {
        $this->merk = $merk;
        $this->tahun = $tahun;
    }
}
?>
```

#### Cara penggunaan:
```php
$mobil1 = new Mobil(); // Menggunakan nilai default
$mobil2 = new Mobil("Honda", 2022); // Menggunakan nilai yang ditentukan
```

---

### **7. Go**
Di Go, constructor tidak secara eksplisit didefinisikan, tetapi biasanya menggunakan fungsi `New` untuk menginisialisasi objek.

#### Contoh:
```go
package main

import "fmt"

type Mobil struct {
    Merk  string
    Tahun int
}

// Constructor (fungsi New)
func NewMobil

---

