function applyDefaults(date, type) {
    // ค่า Default Time
    const defaults = {
      default1: { start: "10:30", end: "19:30" },
      default2: { start: "11:00", end: "17:00" }
    };
  
    // ค่าที่ต้องการเปลี่ยน
    const startTime = defaults[type].start;
    const endTime = defaults[type].end;
  
    // หาแถวที่ตรงกับ data-date
    const row = document.querySelector(`tr[data-date='${date}']`);
    if (row) {
      // เปลี่ยนค่าของ input ในแถวนั้น
      const inputs = row.querySelectorAll(".start, .end");
      for (let i = 0; i < inputs.length; i++) {
        if (i % 2 === 0) {
          inputs[i].value = startTime; // Start
        } else {
          inputs[i].value = endTime;  // End
        }
      }
    }
  }
  