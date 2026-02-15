package demo;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.BufferedReader;
import java.io.InputStreamReader;

public class DemoNotInfected_Sanitize {
    private static final Logger log = LogManager.getLogger(DemoNotInfected_Sanitize.class);

    public static void main(String[] args) throws Exception {
        System.out.print("Type something: ");
        String userInput = new BufferedReader(new InputStreamReader(System.in)).readLine();

        String safe = neutralizeLookups(userInput);

        log.error("User message: {}", safe);
        System.out.println("Done.");
    }

    static String neutralizeLookups(String s) {
        if (s == null) return null;
        // Neutralizza l’inizio del lookup: demo-friendly (non è “la” soluzione definitiva)
        return s.replace("${", "\\${");
    }
}
