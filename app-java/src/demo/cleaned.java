package demo;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.BufferedReader;
import java.io.InputStreamReader;

public class DemoNotInfected_NoLookups {

    // Deve essere impostata PRIMA della creazione del logger / init log4j
    static {
        System.setProperty("log4j2.formatMsgNoLookups", "true");
    }

    private static final Logger log = LogManager.getLogger(DemoNotInfected_NoLookups.class);

    public static void main(String[] args) throws Exception {
        System.out.print("Type something: ");
        String userInput = new BufferedReader(new InputStreamReader(System.in)).readLine();

        // Stesso “pattern” del caso infetto
        log.error("User message: " + userInput);
        log.warn("User message param: {}", userInput);

        System.out.println("Done.");
    }
}
